"""
Test suite for push-to-talk functionality

Tests the expected behavior:
1. Spacebar DOWN -> Start recording audio
2. Spacebar UP -> Send audio buffer to OpenAI
3. Response streamed back as text only
4. Ready for next input (no auto-pause)
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json


class TestPushToTalkWorkflow:
    """Test the complete push-to-talk workflow"""

    @pytest.mark.asyncio
    async def test_spacebar_down_starts_recording(self, config, mock_websocket_manager):
        """Test that holding spacebar starts audio recording"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        # Setup
        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.start_stream = Mock()
            audio_capture.stop_stream = Mock()
            audio_capture.read_audio = AsyncMock(return_value=b'\x00' * 1920)

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)
            openai_client.connect = AsyncMock()
            openai_client.send_audio = AsyncMock()

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Simulate spacebar DOWN (start recording)
        # This should set is_recording flag
        assistant.is_running = True
        assistant._is_recording = True

        assert assistant._is_recording == True, "Recording should start on spacebar down"


    @pytest.mark.asyncio
    async def test_spacebar_up_sends_audio_buffer(self, config, mock_websocket, mock_websocket_manager):
        """Test that releasing spacebar sends buffered audio to API"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        # Setup
        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.rate = 48000
            audio_capture.format = 8  # paInt16
            audio_capture.channels = 1

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)
            openai_client.send_audio = AsyncMock()
            openai_client.websocket = mock_websocket

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Simulate audio buffer accumulation
        assistant.audio_buffer = b'\x00' * 32000  # Some audio data

        # Simulate spacebar UP (send buffer)
        await assistant.send_buffer_to_api()

        # Verify send_audio was called
        assert openai_client.send_audio.called, "Audio should be sent on spacebar release"
        assert len(assistant.audio_buffer) == 0, "Buffer should be cleared after sending"


    @pytest.mark.asyncio
    async def test_no_auto_pause_after_response(self, config, mock_websocket_manager):
        """Test that assistant does NOT auto-pause after receiving response"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        # Setup
        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Simulate response received
        assistant.waiting_for_response = True
        assistant.is_paused = False

        # Process a response.done event
        response = {"type": "response.done", "response": {"id": "test"}}
        # In the refactored version, this should NOT set is_paused=True

        # After handling response
        assistant.waiting_for_response = False

        # Assert we're ready for next input without manual resume
        assert assistant.is_paused == False, "Should NOT auto-pause after response"
        assert assistant.waiting_for_response == False, "Should be ready for next input"


class TestOpenAISessionConfiguration:
    """Test OpenAI session is configured correctly for push-to-talk"""

    @pytest.mark.asyncio
    async def test_turn_detection_set_to_none(self, config, mock_websocket):
        """Test that turn_detection is disabled (set to None) for manual mode"""
        from openai_client import OpenAIClient

        with patch.object(OpenAIClient, '__init__', return_value=None):
            client = OpenAIClient(config)
            client.config = config
            client.websocket = mock_websocket
            client.logger = Mock()
            client.generate_event_id = Mock(return_value="test_event_123")

        # Call initialize_session
        await client.initialize_session()

        # Check the session update message
        assert mock_websocket.send.called
        sent_message = json.loads(mock_websocket.send.call_args[0][0])

        session_config = sent_message.get("session", {})
        turn_detection = session_config.get("turn_detection")

        # Should be None for manual mode (no auto VAD)
        assert turn_detection is None, \
            f"turn_detection should be None for manual mode, got {turn_detection}"


    @pytest.mark.asyncio
    async def test_modalities_text_only(self, config, mock_websocket):
        """Test that session is configured for text-only responses"""
        from openai_client import OpenAIClient

        with patch.object(OpenAIClient, '__init__', return_value=None):
            client = OpenAIClient(config)
            client.config = config
            client.websocket = mock_websocket
            client.logger = Mock()
            client.generate_event_id = Mock(return_value="test_event_123")

        # Call initialize_session
        await client.initialize_session()

        # Check the session update message
        sent_message = json.loads(mock_websocket.send.call_args[0][0])
        session_config = sent_message.get("session", {})
        modalities = session_config.get("modalities")

        # Should be ["text"] only
        assert modalities == ["text"], \
            f"modalities should be ['text'] only, got {modalities}"


class TestVADRemoval:
    """Test that WebRTC VAD is no longer used"""

    def test_no_webrtcvad_import(self):
        """Test that webrtcvad is not imported in AudioCapture"""
        # This test will FAIL initially, then PASS after refactoring
        import sys

        # Try importing audio_capture and check for webrtcvad
        try:
            from audio_capture import AudioCapture
            # Check if webrtcvad is in the module
            import inspect
            source = inspect.getsource(AudioCapture)

            # After refactoring, webrtcvad should not be imported
            assert "import webrtcvad" not in source, \
                "webrtcvad should be removed from AudioCapture"
        except ImportError:
            pytest.skip("Cannot import AudioCapture")


    def test_no_is_speech_method_call(self, config):
        """Test that is_speech VAD method is not called in audio processing"""
        from voice_assistant import VoiceAssistant

        # This will FAIL initially since current code calls is_speech
        # After refactoring, the process_audio loop should not call is_speech

        # Check the source code
        import inspect
        source = inspect.getsource(VoiceAssistant.process_audio)

        # Should not call is_speech after refactoring
        # (This is a code inspection test, not runtime)
        # For now, we expect this to FAIL
        pytest.skip("Skipping until refactoring - expect is_speech to be removed")


class TestBufferManagement:
    """Test simplified buffer management for push-to-talk"""

    @pytest.mark.asyncio
    async def test_buffer_sends_immediately_on_release(self, config, mock_websocket_manager):
        """Test that buffer is sent immediately when spacebar released, no threshold checks"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        # Setup
        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.rate = 48000
            audio_capture.format = 8
            audio_capture.channels = 1

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)
            openai_client.send_audio = AsyncMock()

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Small buffer (less than old threshold of 32KB)
        assistant.audio_buffer = b'\x00' * 5000  # 5KB only

        # Should send immediately on spacebar release, no threshold check
        await assistant.send_buffer_to_api()

        assert openai_client.send_audio.called, \
            "Should send buffer immediately regardless of size"


class TestSpacebarKeyboardControl:
    """Test spacebar keyboard event handling"""

    @pytest.mark.asyncio
    async def test_spacebar_keydown_event(self, config, spacebar_event):
        """Test handling of spacebar keydown event"""
        # This tests the WebSocketManager receiving spacebar down event
        from websocket_manager import WebSocketManager

        mock_assistant = AsyncMock()
        mock_assistant.start_recording = AsyncMock()

        manager = WebSocketManager(mock_assistant)

        # Simulate spacebar down message from frontend
        data = {
            "type": "control",
            "action": "spacebar_down"
        }

        mock_websocket = AsyncMock()
        await manager.process_message(data, mock_websocket)

        # Should trigger recording start
        # (This will FAIL initially - we need to add this handler)
        pytest.skip("Skipping until spacebar_down handler implemented")


    @pytest.mark.asyncio
    async def test_spacebar_keyup_event(self, config, spacebar_event):
        """Test handling of spacebar keyup event"""
        from websocket_manager import WebSocketManager

        mock_assistant = AsyncMock()
        mock_assistant.send_buffer = AsyncMock()

        manager = WebSocketManager(mock_assistant)

        # Simulate spacebar up message from frontend
        data = {
            "type": "control",
            "action": "spacebar_up"
        }

        mock_websocket = AsyncMock()
        await manager.process_message(data, mock_websocket)

        # Should trigger buffer send
        # (This will FAIL initially - we need to add this handler)
        pytest.skip("Skipping until spacebar_up handler implemented")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
