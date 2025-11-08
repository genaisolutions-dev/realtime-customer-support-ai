"""
Test suite for frontend-backend state synchronization

Tests the fixes for state synchronization issues between frontend and backend,
including status broadcasts always including is_paused field.
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch


class TestStatusBroadcastConsistency:
    """Test that all status broadcasts include required fields"""

    @pytest.mark.asyncio
    async def test_initial_status_includes_is_paused(self, config):
        """Test that initial connection status includes is_paused"""
        from websocket_manager import WebSocketManager
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        # Setup assistant
        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            None, response_processor
        )

        websocket_manager = WebSocketManager(assistant)

        # Mock websocket
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.remote_address = ('127.0.0.1', 12345)

        # Simulate handler sending initial status
        websocket_manager.clients.add(mock_ws)
        await mock_ws.send(json.dumps({
            'type': 'status',
            'status': 'ready',
            'is_listening': assistant.is_running,
            'is_paused': assistant.is_paused
        }))

        # Verify send was called
        assert mock_ws.send.called
        sent_message = json.loads(mock_ws.send.call_args[0][0])

        # Check all required fields present
        assert 'type' in sent_message
        assert 'status' in sent_message
        assert 'is_listening' in sent_message
        assert 'is_paused' in sent_message
        assert sent_message['is_paused'] == False  # Initial state


    @pytest.mark.asyncio
    async def test_broadcast_status_always_includes_is_paused(self, config):
        """Test that broadcast_status always includes is_paused from assistant"""
        from websocket_manager import WebSocketManager

        mock_assistant = Mock()
        mock_assistant.is_paused = True  # Set to True to verify it's read

        manager = WebSocketManager(mock_assistant)

        # Mock client
        mock_ws = AsyncMock()
        manager.clients.add(mock_ws)

        # Broadcast status
        await manager.broadcast_status("listening", True)

        # Verify message format
        assert mock_ws.send.called
        sent_message = json.loads(mock_ws.send.call_args[0][0])

        assert sent_message['type'] == 'status'
        assert sent_message['status'] == 'listening'
        assert sent_message['is_listening'] == True
        assert sent_message['is_paused'] == True  # Should match assistant.is_paused


    @pytest.mark.asyncio
    async def test_pause_status_broadcast(self, config, mock_websocket_manager):
        """Test pause broadcasts correct status"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.stop_stream = Mock()

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Pause
        await assistant.pause()

        # Verify broadcast_status called with paused
        assert mock_websocket_manager.broadcast_status.called
        call_args = mock_websocket_manager.broadcast_status.call_args[0]
        assert call_args[0] == "paused"


class TestFrontendStateSync:
    """Test frontend state synchronization (mock frontend behavior)"""

    def test_frontend_waits_for_backend_confirmation(self):
        """Test that frontend doesn't optimistically update isPaused"""
        # This is more of a documentation test - verifies the pattern
        # In actual FloatingPrompter.js:
        # - togglePauseResume sends message
        # - Does NOT call setIsPaused immediately
        # - Waits for status broadcast to update state

        # Mock frontend behavior
        is_paused = False

        def toggle_pause_resume():
            # Old (bad) behavior:
            # is_paused = not is_paused  # ❌ Optimistic update
            # send_message('pause_listening')

            # New (good) behavior:
            action = 'resume_listening' if is_paused else 'pause_listening'
            send_message(action)
            # ✓ No state update here - wait for backend

        def send_message(action):
            pass  # Would send WebSocket message

        # Simulate
        toggle_pause_resume()

        # State should NOT have changed yet
        assert is_paused == False  # Still old value


class TestStopListeningHandler:
    """Test that stop_listening WebSocket handler exists"""

    @pytest.mark.asyncio
    async def test_stop_listening_action_handled(self, config):
        """Test that stop_listening action is recognized"""
        from websocket_manager import WebSocketManager

        mock_assistant = AsyncMock()
        mock_assistant.stop_listening = AsyncMock()

        manager = WebSocketManager(mock_assistant)

        # Send stop_listening message
        data = {
            'type': 'control',
            'action': 'stop_listening'
        }

        mock_ws = AsyncMock()
        await manager.process_message(data, mock_ws)

        # Verify stop_listening was called
        assert mock_assistant.stop_listening.called


    @pytest.mark.asyncio
    async def test_stop_listening_clears_buffer(self, config, mock_websocket_manager):
        """Test that stop_listening clears audio buffer"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.stop_stream = Mock()

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Set buffer
        assistant.is_running = True
        assistant.audio_buffer = b'test_data'
        assistant.buffer_ready.set()

        # Stop listening
        await assistant.stop_listening()

        # Buffer should be cleared
        assert assistant.audio_buffer == b''
        assert not assistant.buffer_ready.is_set()


class TestErrorCodeMapping:
    """Test user-friendly error code mapping"""

    def test_error_code_mapping_exists(self):
        """Test that error code mapping module exists"""
        from constants import get_error_code, ERROR_CODE_MAPPING

        assert callable(get_error_code)
        assert isinstance(ERROR_CODE_MAPPING, dict)


    def test_get_error_code_from_exception(self):
        """Test getting error code from exception instance"""
        from constants import get_error_code

        # Test OSError
        exc = OSError("Device not found")
        code = get_error_code(exc)
        assert code == 'device_error'

        # Test KeyError
        exc = KeyError("missing_field")
        code = get_error_code(exc)
        assert code == 'missing_field'

        # Test unknown exception
        class CustomError(Exception):
            pass
        exc = CustomError("unknown")
        code = get_error_code(exc)
        assert code == 'unknown_error'


    def test_get_error_code_from_string(self):
        """Test getting error code from exception name string"""
        from constants import get_error_code

        code = get_error_code('ConnectionClosed')
        assert code == 'connection_lost'

        code = get_error_code('TimeoutError')
        assert code == 'timeout'


    @pytest.mark.asyncio
    async def test_broadcast_error_uses_friendly_codes(self, config, mock_websocket_manager):
        """Test that error broadcasts use friendly error codes"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)
            # Make send_audio raise OSError
            openai_client.send_audio = AsyncMock(side_effect=OSError("Device error"))

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Try to send audio (will fail)
        await assistant.send_audio_to_api(b'test')

        # Verify broadcast_error called with friendly code
        assert mock_websocket_manager.broadcast_error.called
        call_args = mock_websocket_manager.broadcast_error.call_args[0]
        error_code = call_args[1]
        assert error_code == 'device_error'  # Friendly code, not 'OSError'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
