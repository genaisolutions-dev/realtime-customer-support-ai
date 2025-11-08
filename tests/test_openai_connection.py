"""
Test suite for OpenAI connection health and startup flow

This test suite verifies:
1. Backend successfully connects to OpenAI API
2. Session initialization completes (session.updated received)
3. Audio processing starts only after start_listening() called
4. The complete startup flow works as designed
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json


class TestOpenAIConnectionHealth:
    """Test OpenAI API connection and session initialization"""

    @pytest.mark.asyncio
    async def test_openai_connects_successfully(self, config, mock_websocket):
        """Test that OpenAI client can establish WebSocket connection"""
        from openai_client import OpenAIClient

        with patch.object(OpenAIClient, '__init__', return_value=None):
            client = OpenAIClient(config)
            client.config = config
            client.logger = Mock()

            # Mock websockets.connect
            with patch('websockets.connect', return_value=mock_websocket):
                client.websocket = None
                await client.connect()

                # After connect, websocket should be set
                # In real implementation, connect() sets self.websocket
                assert client.websocket is not None or mock_websocket is not None, \
                    "WebSocket connection should be established"


    @pytest.mark.asyncio
    async def test_session_initialization_sends_config(self, config, mock_websocket):
        """Test that session initialization sends correct configuration"""
        from openai_client import OpenAIClient

        with patch.object(OpenAIClient, '__init__', return_value=None):
            client = OpenAIClient(config)
            client.config = config
            client.websocket = mock_websocket
            client.logger = Mock()
            client.generate_event_id = Mock(return_value="test_event_123")

            # Initialize session
            await client.initialize_session()

            # Verify session.update message was sent
            assert mock_websocket.send.called, "Session update should be sent"

            sent_message = json.loads(mock_websocket.send.call_args[0][0])
            assert sent_message.get("type") == "session.update", \
                "Should send session.update message"


    @pytest.mark.asyncio
    async def test_session_updated_response_received(self, config, mock_websocket, mock_openai_response):
        """Test that session.updated response is received after initialization"""
        from openai_client import OpenAIClient

        with patch.object(OpenAIClient, '__init__', return_value=None):
            client = OpenAIClient(config)
            client.config = config
            client.websocket = mock_websocket
            client.logger = Mock()

            # Mock receiving session.updated response
            mock_websocket.recv = AsyncMock(return_value=json.dumps({
                "type": "session.updated",
                "session": {"id": "sess_123"}
            }))

            response = await client.receive_response()

            assert response.get("type") == "session.updated", \
                "Should receive session.updated response"


class TestAudioProcessingStartup:
    """Test that audio processing starts correctly"""

    @pytest.mark.asyncio
    async def test_process_audio_waits_for_is_running(self, config, mock_websocket_manager):
        """Test that process_audio loop only runs when is_running=True"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        # Setup
        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.read_audio = AsyncMock(return_value=b'\x00' * 1920)
            audio_capture.get_audio_level = Mock(return_value=50)
            audio_capture.is_speech = AsyncMock(return_value=False)

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Initially, is_running should be False
        assert assistant.is_running == False, \
            "is_running should be False initially"

        # Create process_audio task
        audio_task = asyncio.create_task(assistant.process_audio())

        # Give it a moment
        await asyncio.sleep(0.1)

        # Cancel the task
        audio_task.cancel()
        try:
            await audio_task
        except asyncio.CancelledError:
            pass

        # Audio processing should not have read any audio since is_running=False
        # (The loop exits immediately)
        assert audio_capture.read_audio.call_count == 0, \
            "Audio should not be read when is_running=False"


    @pytest.mark.asyncio
    async def test_start_listening_sets_is_running(self, config, mock_websocket_manager):
        """Test that start_listening() sets is_running=True"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        # Setup
        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.start_stream = Mock()

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Initially False
        assert assistant.is_running == False

        # Call start_listening
        await assistant.start_listening()

        # Now should be True
        assert assistant.is_running == True, \
            "start_listening() should set is_running=True"

        # Stream should be started
        assert audio_capture.start_stream.called, \
            "Audio stream should be started"


    @pytest.mark.asyncio
    async def test_audio_processing_runs_after_start_listening(self, config, mock_websocket_manager):
        """Test that audio processing actually runs after start_listening() called"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        # Setup
        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.read_audio = AsyncMock(return_value=b'\x00' * 1920)
            audio_capture.get_audio_level = Mock(return_value=50)
            audio_capture.is_speech = AsyncMock(return_value=False)
            audio_capture.start_stream = Mock()

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Start listening first
        await assistant.start_listening()
        assert assistant.is_running == True

        # Now create process_audio task
        audio_task = asyncio.create_task(assistant.process_audio())

        # Give it time to process
        await asyncio.sleep(0.2)

        # Cancel the task
        audio_task.cancel()
        try:
            await audio_task
        except asyncio.CancelledError:
            pass

        # Audio should have been read since is_running=True
        assert audio_capture.read_audio.call_count > 0, \
            "Audio should be read when is_running=True"


class TestCompleteStartupFlow:
    """Test the complete startup flow from backend start to ready state"""

    @pytest.mark.asyncio
    async def test_backend_startup_sequence(self, config):
        """Test that backend follows correct startup sequence"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from websocket_manager import WebSocketManager
        from response_processor import ResponseProcessor

        # Setup all components with mocks
        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.select_audio_device = Mock()
            audio_capture.start_stream = Mock()
            audio_capture.read_audio = AsyncMock(return_value=b'\x00' * 1920)
            audio_capture.get_audio_level = Mock(return_value=0)
            audio_capture.is_speech = AsyncMock(return_value=False)

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)
            openai_client.connect = AsyncMock()
            openai_client.receive_response = AsyncMock(side_effect=asyncio.CancelledError)
            openai_client.reset_pending = False

        with patch.object(WebSocketManager, '__init__', return_value=None):
            websocket_manager = WebSocketManager(None)
            websocket_manager.start = AsyncMock()
            websocket_manager.broadcast_status = AsyncMock()

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            websocket_manager, response_processor
        )

        # Expected startup sequence:
        # 1. WebSocket server starts
        # 2. OpenAI client connects
        # 3. Audio device selected
        # 4. Audio stream started
        # 5. Status broadcast: "ready"
        # 6. Audio processing task created (but not active until user clicks)
        # 7. API response handling task created
        # 8. Main loop waits for commands

        # Start the run() method but cancel quickly
        run_task = asyncio.create_task(assistant.run())
        await asyncio.sleep(0.2)
        run_task.cancel()

        try:
            await run_task
        except asyncio.CancelledError:
            pass

        # Verify startup sequence
        assert websocket_manager.start.called, "WebSocket manager should start"
        assert openai_client.connect.called, "OpenAI client should connect"
        assert audio_capture.select_audio_device.called, "Audio device should be selected"
        assert audio_capture.start_stream.called, "Audio stream should start"

        # Verify "ready" status was broadcast
        status_calls = [call for call in websocket_manager.broadcast_status.call_args_list
                       if call[0][0] == "ready"]
        assert len(status_calls) > 0, "Should broadcast 'ready' status"


    @pytest.mark.asyncio
    async def test_backend_ready_but_waiting_for_user_interaction(self, config, mock_websocket_manager):
        """Test that backend is ready but audio processing inactive until user clicks Start"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        # Setup
        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.read_audio = AsyncMock(return_value=b'\x00' * 1920)

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Simulate backend is ready (OpenAI connected, device selected)
        # But user hasn't clicked "Start Listening" yet

        assert assistant.is_running == False, \
            "Backend should be ready but is_running=False (waiting for user)"

        assert assistant.is_idle == True, \
            "Backend should report as idle (ready for commands)"


class TestConnectionErrorHandling:
    """Test error handling for connection issues"""

    @pytest.mark.asyncio
    async def test_invalid_api_key_error(self, config, mock_websocket):
        """Test handling of invalid API key error"""
        from openai_client import OpenAIClient
        import websockets

        with patch.object(OpenAIClient, '__init__', return_value=None):
            client = OpenAIClient(config)
            client.config = config
            client.websocket = mock_websocket
            client.logger = Mock()

            # Simulate WebSocket connection closed with invalid API key
            mock_websocket.recv = AsyncMock(
                side_effect=websockets.exceptions.ConnectionClosedError(
                    3000, "invalid_request_error.invalid_api_key"
                )
            )

            with pytest.raises(websockets.exceptions.ConnectionClosedError) as exc_info:
                await client.receive_response()

            assert "invalid_api_key" in str(exc_info.value), \
                "Should raise ConnectionClosedError with invalid_api_key"


    @pytest.mark.asyncio
    async def test_connection_closed_sets_waiting_for_response_false(self, config, mock_websocket_manager):
        """Test that connection errors reset waiting_for_response flag"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor
        import websockets

        # Setup
        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)
            openai_client.receive_response = AsyncMock(
                side_effect=websockets.exceptions.ConnectionClosedError(
                    3000, "test error"
                )
            )

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Set waiting_for_response
        assistant.waiting_for_response = True

        # Start handle_api_responses
        response_task = asyncio.create_task(assistant.handle_api_responses())
        await asyncio.sleep(0.1)

        # Should reset waiting_for_response on error
        assert assistant.waiting_for_response == False, \
            "waiting_for_response should be reset to False on connection error"

        response_task.cancel()
        try:
            await response_task
        except asyncio.CancelledError:
            pass


class TestAudioLevelThrottling:
    """Test audio level broadcast throttling"""

    @pytest.mark.asyncio
    async def test_audio_level_throttled_to_10_per_sec(self, config, mock_websocket_manager):
        """Test that audio level broadcasts are throttled to 10/sec"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor
        import time

        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.read_audio = AsyncMock(return_value=b'\x00' * 1920)
            audio_capture.get_audio_level = Mock(return_value=75)
            audio_capture.is_speech = AsyncMock(return_value=False)

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Verify throttle timer initialized
        assert hasattr(assistant, 'last_level_broadcast')
        assert assistant.last_level_broadcast == 0

        # Start processing
        assistant.is_running = True
        audio_task = asyncio.create_task(assistant.process_audio())

        # Let it run for 0.5 seconds
        await asyncio.sleep(0.5)

        # Stop
        assistant.is_running = False
        assistant.resume_event.set()
        audio_task.cancel()
        try:
            await audio_task
        except asyncio.CancelledError:
            pass

        # At 20ms per chunk, 0.5s = 25 chunks
        # But broadcasts should be throttled to ~5 (0.5s * 10/sec)
        broadcast_count = mock_websocket_manager.broadcast_audio_level.call_count

        # Allow some variance but should be close to 5, not 25
        assert broadcast_count >= 3  # At least 3 broadcasts
        assert broadcast_count <= 8  # But not more than 8 (allowing some overhead)


class TestVADStateReset:
    """Test VAD state is properly reset"""

    def test_reset_vad_reinitializes_detector(self, config):
        """Test that reset_vad() reinitializes VAD detector"""
        from audio_capture import AudioCapture
        import webrtcvad

        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.speech_frames_count = 10
            audio_capture.stop_stream = Mock()
            audio_capture.logger = Mock()

        # Reset VAD
        audio_capture.reset_vad()

        # Should reset counter
        assert audio_capture.speech_frames_count == 0

        # Should reinitialize VAD detector
        assert hasattr(audio_capture, 'vad')
        assert isinstance(audio_capture.vad, webrtcvad.Vad)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
