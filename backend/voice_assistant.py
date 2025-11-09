import asyncio
import os
import time
import websockets
import pyaudio
from dotenv import load_dotenv
from audio_capture import AudioCapture
from openai_client import OpenAIClient
from websocket_manager import WebSocketManager
from response_processor import ResponseProcessor
from config import Config
from common_logging import setup_logging
from constants import get_error_code

class VoiceAssistant:
    def __init__(self, config: Config, audio_capture: AudioCapture, openai_client: OpenAIClient,
                 websocket_manager: WebSocketManager, response_processor: ResponseProcessor):
        self.config = config
        self.max_api_calls = config.max_api_calls
        self.api_calls_made = 0
        self.is_running = False
        self.waiting_for_response = False
        self.audio_buffer = b""
        self.silence_threshold = config.silence_threshold
        self.cooldown_active = False
        self.cooldown_duration = config.cooldown_duration
        self.min_buffer_size = config.min_buffer_size
        self.max_buffer_wait_time = config.max_buffer_wait_time
        self.buffer_ready = asyncio.Event()
        self.resume_event = asyncio.Event()  # Event for efficient pause waiting
        self.resume_event.set()  # Initially set (not paused)
        self.last_audio_time = 0
        self.last_level_broadcast = 0  # Throttle audio level broadcasts
        self.buffer_lock = asyncio.Lock()  # Protect audio buffer from race conditions

        self.audio_capture = audio_capture
        self.openai_client = openai_client
        self.websocket_manager = websocket_manager
        self.response_processor = response_processor

        self.logger = setup_logging('voice_assistant')
        self.logger.info("VoiceAssistant initialized")

        self.process_audio_task = None
        self.cooldown_task = None  # Track cooldown task for cancellation
        self.is_paused = False
        self._is_idle = True
        self._is_recording = False
        self._is_processing = False

    async def pause(self):
        if self.is_paused:
            return  # Already paused
        self.is_paused = True  # Set the paused flag
        self.resume_event.clear()  # Clear event to block audio processing

        # Cancel any active cooldown
        if self.cooldown_task and not self.cooldown_task.done():
            self.cooldown_task.cancel()
            self.cooldown_active = False
            self.logger.debug("Cooldown task cancelled due to pause")

        self.audio_capture.stop_stream()  # Stop the audio stream
        self.logger.info("Assistant paused")

        # If there's audio in the buffer, send it to the API
        async with self.buffer_lock:  # Protect buffer access
            if self.audio_buffer:
                await self.send_buffer_to_api()
                # Clear the buffer and reset variables
                self.audio_buffer = b''
                self.buffer_ready.clear()

        # Broadcast paused status
        await self.websocket_manager.broadcast_status("paused", False)

    async def resume(self):
        if not self.is_paused:
            return  # Already running
        self.is_paused = False  # Reset the paused flag
        self.resume_event.set()  # Signal audio processing to continue
        self.audio_buffer = b''  # Clear the audio buffer
        self.audio_capture.reset_vad()  # Reset VAD state
        self.last_audio_time = time.time()  # Reset the last audio time
        self.waiting_for_response = False  # Ensure not waiting for a response
        self.cooldown_active = False  # Reset cooldown if necessary
        self.audio_capture.start_stream()  # Start the audio stream
        await self.websocket_manager.broadcast_status("listening", True)  # Broadcast listening status
        self.logger.info("Assistant resumed")

    @property
    def is_idle(self):
        return (not self._is_recording and 
                not self._is_processing and 
                not self.waiting_for_response and 
                not self.cooldown_active)

    async def run(self):
        try:
            await self.websocket_manager.start()
            await self.openai_client.connect()

            self.audio_capture.select_audio_device()
            # Audio stream will start when user clicks "Start Listening" (in start_listening method)
            self.logger.info("Voice Assistant is ready.")
            print("✓ Voice Assistant is ready. Waiting for frontend to start listening...\n")
            await self.websocket_manager.broadcast_status("ready", False)

            # process_audio_task will be created when user clicks "Start Listening"
            api_task = asyncio.create_task(self.handle_api_responses())

            while True:
                if self.is_idle and self.openai_client.reset_pending:
                    await self.openai_client.reset_session()
                
                await asyncio.sleep(1)  # Check every second

        except websockets.exceptions.ConnectionClosed as e:
            self.logger.error(f"WebSocket connection closed: {str(e)}")
            self.waiting_for_response = False
            self.logger.debug("waiting_for_response set to False")
            await self.websocket_manager.broadcast_status("disconnected", False)
            
            # Attempt to reconnect
            await self.reconnect_openai_client()
        except Exception as e:
            self.logger.exception(f"Error in main loop: {str(e)}")
        finally:
            await self.cleanup()

    async def process_audio(self):
        self.logger.info("Started audio processing")
        try:
            while self.is_running:
                # Wait for resume event if paused (efficient event-based waiting)
                await self.resume_event.wait()

                if not self.is_running:  # Check again after wait
                    break
                try:
                    self._is_recording = True
                    audio_chunk = await self.audio_capture.read_audio()
                    self._is_recording = False

                    # Calculate and broadcast audio level for visual feedback (throttled to 10/sec)
                    current_time = time.time()
                    if current_time - self.last_level_broadcast >= 0.1:  # 100ms = 10 updates/sec
                        audio_level = self.audio_capture.get_audio_level(audio_chunk)
                        await self.websocket_manager.broadcast_audio_level(audio_level)
                        self.last_level_broadcast = current_time

                    self._is_processing = True
                    is_speech = await self.audio_capture.is_speech(audio_chunk)
                    self._is_processing = False

                    # Status broadcasts happen only from start_listening/stop_listening
                    # Removed redundant broadcast here to prevent race condition with stop_listening

                    async with self.buffer_lock:  # Protect buffer access
                        if is_speech:
                            self.audio_buffer += audio_chunk
                            self.last_audio_time = time.time()
                            self.logger.debug(f"Speech detected. Buffer size: {len(self.audio_buffer)}")

                            if len(self.audio_buffer) >= self.min_buffer_size:
                                if not self.buffer_ready.is_set():
                                    await self.websocket_manager.broadcast_debug("Speech detected, buffer ready")
                                self.buffer_ready.set()

                        # REMOVED: VAD-based and timeout-based auto-triggers
                        # For push-to-talk: Buffer only accumulates during listening
                        # API call is triggered ONLY when user presses spacebar (stop_listening)

                    await asyncio.sleep(0.01)
                except Exception as e:
                    self.logger.exception(f"Error in audio processing: {str(e)}")
        except asyncio.CancelledError:
            self.logger.info("Audio processing task cancelled")
        finally:
            self._is_recording = False
            self._is_processing = False
            self.logger.info("Stopped audio processing")

    def _resample_audio_sync(self, audio_buffer):
        """Synchronous audio resampling (runs in thread pool to avoid blocking event loop)"""
        from pydub import AudioSegment

        audio_segment = AudioSegment(
            data=audio_buffer,
            sample_width=pyaudio.get_sample_size(self.audio_capture.format),
            frame_rate=self.audio_capture.rate,
            channels=self.audio_capture.channels
        )
        audio_segment = audio_segment.set_frame_rate(24000)
        audio_segment = audio_segment.set_channels(1)
        return audio_segment.raw_data

    async def send_buffer_to_api(self):
        if len(self.audio_buffer) == 0:
            self.logger.info("Audio buffer is empty. Not sending to API.")
            self.audio_buffer = b""
            self.buffer_ready.clear()
            return

        try:
            self.waiting_for_response = True  # Set before sending to prevent new API calls
            await self.websocket_manager.broadcast_new_response()

            # Resample audio asynchronously in thread pool (non-blocking)
            loop = asyncio.get_event_loop()
            resampled_audio_buffer = await loop.run_in_executor(
                None,
                self._resample_audio_sync,
                self.audio_buffer
            )

            await self.send_audio_to_api(resampled_audio_buffer)
            self.audio_buffer = b""
            self.buffer_ready.clear()
            # No cooldown - ready for next capture immediately
        except Exception as e:
            self.logger.error(f"Error in send_buffer_to_api: {str(e)}", exc_info=True)

    async def send_audio_to_api(self, buffer):
        if self.max_api_calls != -1 and self.api_calls_made >= self.max_api_calls:
            self.logger.info("Maximum number of API calls reached. Initiating graceful shutdown.")
            await self.websocket_manager.broadcast_status("max_calls_reached", False)
            return False

        self.logger.info(f"Sending audio buffer to API (size: {len(buffer)} bytes)")
        self.logger.debug(f"waiting_for_response: {self.waiting_for_response}, cooldown_active: {self.cooldown_active}")

        try:
            await self.websocket_manager.broadcast_debug("Sending audio to OpenAI API...")
            await self.openai_client.send_audio(buffer)
            self.api_calls_made += 1
            self.logger.info(f"API call made. Total calls: {self.api_calls_made}")
            await self.websocket_manager.broadcast_api_call_count(self.api_calls_made)
            await self.websocket_manager.broadcast_status("processing", False)
            # No auto-pause - keep listening for next utterance (user controls via spacebar)
            return True
        except Exception as e:
            self.logger.error(f"Error sending audio to API: {str(e)}", exc_info=True)
            await self.websocket_manager.broadcast_error(str(e), get_error_code(e))
            return False
        finally:
            self.logger.debug("Exiting send_audio_to_api")

    async def cooldown_timer(self):
        self.logger.debug(f"Cooldown started for {self.cooldown_duration} seconds")
        await asyncio.sleep(self.cooldown_duration)
        self.cooldown_active = False
        self.logger.debug("Cooldown period ended")

    async def handle_api_responses(self):
        self.logger.info("Started handling API responses")
        try:
            while True:
                try:
                    # Only apply timeout when actively waiting for a response
                    # This prevents false timeouts during normal idle periods
                    if self.waiting_for_response:
                        # Expecting response - use timeout to detect connection stalls
                        response = await asyncio.wait_for(
                            self.openai_client.receive_response(),
                            timeout=30.0
                        )
                    else:
                        # Idle - no timeout, wait indefinitely for next activity
                        response = await self.openai_client.receive_response()
                except asyncio.TimeoutError:
                    # Only triggers if response expected but not received within 30s
                    self.logger.error("API response timeout (30s) - reconnecting to OpenAI...")
                    await self.openai_client.reset_session()
                    await self.websocket_manager.broadcast_debug("Connection timeout - reconnecting...")
                    continue

                if not isinstance(response, dict):
                    self.logger.error(f"Invalid API response type: {type(response)}")
                    continue

                if response['type'] == 'session_reset':
                    self.logger.info("Session was reset. Restarting the conversation.")
                    self.waiting_for_response = False
                    await self.websocket_manager.broadcast_status("ready", False)
                    continue

                # Forward the response to the frontend
                await self.websocket_manager.broadcast_response(response)

                if response['type'] == 'response.audio_transcript.delta':
                    # Process delta for internal tracking (frontend gets delta via broadcast_response above)
                    delta = self.response_processor.process_transcript_delta(response.get('delta', ''))
                    # Duplicate broadcast removed - frontend already receives delta in 'response' message
                    # Question detection removed - was unused dead code
                elif response['type'] == 'response.done':
                    self.logger.info("Response complete")
                    await self.websocket_manager.broadcast_debug("AI response received")
                    self.waiting_for_response = False
                    self.logger.debug("waiting_for_response set to False")
                    await self.websocket_manager.broadcast_status("idle", False)
                    self.response_processor.clear_transcript()
                elif response['type'] == 'error':
                    error_message = response.get('error', {}).get('message', 'Unknown error')
                    error_code = response.get('error', {}).get('code', 'Unknown code')
                    self.logger.error(f"API Error: Code: {error_code}, Message: {error_message}")
                    self.waiting_for_response = False
                    self.logger.debug("waiting_for_response set to False")
                    await self.websocket_manager.broadcast_status("error", False)
                    if error_code == 'session_expired':
                        self.logger.info("Session expired. Attempting to reconnect.")
                        await self.openai_client.reset_session()
                        await self.websocket_manager.broadcast_status("ready", False)
                else:
                    self.logger.debug(f"Received response type: {response['type']}")
        except asyncio.CancelledError:
            self.logger.info("API response handling task cancelled")
        except Exception as e:
            self.logger.error(f"Error handling API response: {str(e)}", exc_info=True)
            self.waiting_for_response = False
            self.logger.debug("waiting_for_response set to False")
            await self.websocket_manager.broadcast_error(str(e), get_error_code(e))

    async def reconnect_openai_client(self):
        self.logger.info("Attempting to reconnect to OpenAI API")
        reconnect_attempts = 0
        max_reconnect_attempts = 3

        while reconnect_attempts < max_reconnect_attempts:
            try:
                await self.openai_client.connect()
                await self.openai_client.initialize_session()
                self.logger.info("Reconnected to OpenAI API")
                return
            except Exception as e:
                reconnect_attempts += 1
                self.logger.error(f"Reconnection attempt {reconnect_attempts} failed: {str(e)}")
                await asyncio.sleep(2)

        self.logger.error("Maximum reconnection attempts reached. Stopping assistant.")
        await self.graceful_shutdown()

    async def graceful_shutdown(self):
        self.logger.info("Initiating graceful shutdown...")
        await self.websocket_manager.broadcast_status("shutting_down", False)

        # Close the OpenAI client connection
        await self.openai_client.close_connection()

        await self.cleanup()
        self.logger.info("Graceful shutdown complete")

    async def start_listening(self):
        if not self.is_running:
            # Clear any stale buffered audio from before user clicked "Start Listening"
            self.audio_buffer = b""
            self.buffer_ready.clear()

            self.is_running = True
            self.logger.info("VoiceAssistant started listening")
            print("✓ Audio processing started - now listening for speech\n")
            await self.websocket_manager.broadcast_debug("Listening for speech...")
            # Start the audio stream
            self.audio_capture.start_stream()
            self.process_audio_task = asyncio.create_task(self.process_audio())
            # Broadcast status update
            await self.websocket_manager.broadcast_status("listening", True)

    async def stop_listening(self):
        if self.is_running:
            self.is_running = False
            self.logger.info("VoiceAssistant stopped listening")

            # Cancel the process_audio task
            if self.process_audio_task:
                self.process_audio_task.cancel()
                try:
                    await self.process_audio_task
                except asyncio.CancelledError:
                    self.logger.info("process_audio_task successfully cancelled")
                self.process_audio_task = None

            # Push-to-talk: Send buffered audio to API if buffer has content
            async with self.buffer_lock:  # Protect buffer access
                buffer_size = len(self.audio_buffer)
                if buffer_size > 0:
                    self.logger.info(f"Sending buffered audio to API (buffer size: {buffer_size} bytes)")
                    await self.websocket_manager.broadcast_debug(f"Sending {buffer_size} bytes to API...")
                    await self.send_buffer_to_api()
                else:
                    self.logger.info("No audio in buffer - nothing to send")
                    await self.websocket_manager.broadcast_debug("No audio captured")

                # Clear audio buffer and reset state
                self.audio_buffer = b''
                self.buffer_ready.clear()

            # Stop the audio stream
            self.audio_capture.stop_stream()
            # Broadcast status update
            await self.websocket_manager.broadcast_status("idle", False)

    async def cleanup(self):
        # Add any cleanup operations here
        pass

    def stop(self):
        self.is_running = False
        self.logger.info("Voice Assistant stopped")
        # Cancel the process_audio task if it's running
        if self.process_audio_task:
            self.process_audio_task.cancel()
            self.process_audio_task = None

def read_file_input(prompt_text, examples):
    """
    Read context from a file path provided by user.
    Handles Windows/Linux paths, spaces, quotes, etc.
    """
    print(f"\n{prompt_text}")
    print(f"Examples: {examples}")
    print("\nProvide the full path to your file:")
    print("  Windows: C:\\Users\\name\\Documents\\resume.md")
    print("  Linux/Mac: /home/name/documents/resume.md")
    print("  Relative: ./resume.md")
    print("To skip: press Enter")

    file_path = input("\nEnter file path (or press Enter to skip): ").strip()

    # If user just pressed Enter, skip
    if not file_path:
        return ""

    # Remove surrounding quotes if present (users sometimes paste "C:\path")
    if file_path.startswith('"') and file_path.endswith('"'):
        file_path = file_path[1:-1]
    if file_path.startswith("'") and file_path.endswith("'"):
        file_path = file_path[1:-1]

    # Normalize path (handles backslashes, forward slashes, etc.)
    file_path = os.path.normpath(file_path)

    # Check if file exists
    if not os.path.isfile(file_path):
        print(f"✗ File not found: {file_path}")
        print("Skipping context input.")
        return ""

    # Read file content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"✓ Loaded {len(content)} characters from {os.path.basename(file_path)}")
            return content
    except Exception as e:
        print(f"✗ Error reading file: {e}")
        print("Skipping context input.")
        return ""

if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv()

    # Prompt user for model selection
    print("\nAvailable OpenAI Realtime API models:")
    print("=" * 80)
    for key, model in Config.MODELS.items():
        print(f"\n{key}. {model['display_name']}")
        print(f"   Audio Input:  {model['audio_input_price']}")
        print(f"   Audio Output: {model['audio_output_price']}")
        print(f"   Text Input:   {model['text_input_price']}")
        print(f"   Text Output:  {model['text_output_price']}")
    print("=" * 80)

    model_choice = input("\nSelect model (1 or 2) [default: 1]: ").strip()
    if model_choice not in ["1", "2"]:
        print("Invalid selection. Using GPT-4o Realtime (option 1)")
        model_choice = "1"

    # Prompt for optional context to improve AI responses
    print("\n" + "=" * 80)
    print("OPTIONAL: Provide context to improve AI responses")
    print("=" * 80)

    background_context = read_file_input(
        "Background Context: Information about you, your expertise, or relevant background.",
        "resume, profile, skills, experience, product catalog, company policies, FAQs"
    )

    task_context = read_file_input(
        "Task Context: What you're working on or trying to accomplish.",
        "job description, project goals, current objective, known issues, promotions, escalation procedures"
    )

    # Create config with model choice and optional context
    config = Config(model_choice=model_choice,
                    background_context=background_context,
                    task_context=task_context)
    logger = setup_logging('voice_assistant')
    logger.info(f"Selected model: {config.selected_model['display_name']}")

    # Display context configuration status
    if background_context or task_context:
        print("\n✓ Context configured and will be included in AI instructions")
        if background_context:
            logger.info(f"Background context provided ({len(background_context)} chars)")
        if task_context:
            logger.info(f"Task context provided ({len(task_context)} chars)")
    else:
        print("\n✓ No additional context provided")

    # Prompt user for max number of API calls
    max_api_calls_input = input("\nEnter maximum number of API calls (-1 for unlimited): ")
    try:
        config.max_api_calls = int(max_api_calls_input)
        logger.info(f"Max API calls set to: {config.max_api_calls}")
    except ValueError:
        print("Invalid input. Using unlimited API calls.")
        config.max_api_calls = -1
        logger.info("Max API calls set to unlimited")

    audio_capture = AudioCapture(config)
    openai_client = OpenAIClient(config)
    response_processor = ResponseProcessor(config)
    assistant = VoiceAssistant(config, audio_capture, openai_client, None, response_processor)
    websocket_manager = WebSocketManager(assistant)
    assistant.websocket_manager = websocket_manager
    asyncio.run(assistant.run())
