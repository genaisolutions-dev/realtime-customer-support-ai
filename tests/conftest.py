"""
pytest configuration and shared fixtures for test infrastructure
"""
import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, MagicMock
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from config import Config


@pytest.fixture
def config():
    """Create a test configuration"""
    config = Config()
    config.api_key = "sk-test-key-mock"
    config.max_api_calls = -1
    return config


@pytest.fixture
def mock_audio_data():
    """Generate mock audio data (16-bit PCM)"""
    # 100ms of silence at 48kHz, mono, 16-bit
    import struct
    num_samples = int(48000 * 0.1)  # 100ms
    audio_data = struct.pack('<' + 'h' * num_samples, *([0] * num_samples))
    return audio_data


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection"""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.recv = AsyncMock()
    ws.closed = False
    return ws


@pytest.fixture
def mock_openai_response():
    """Generate mock OpenAI Realtime API responses"""
    def _response(response_type="response.audio_transcript.delta", delta="Test response"):
        responses = {
            "session.created": {
                "type": "session.created",
                "session": {"id": "test_session_123"}
            },
            "response.audio_transcript.delta": {
                "type": "response.audio_transcript.delta",
                "delta": delta
            },
            "response.done": {
                "type": "response.done",
                "response": {"id": "resp_123"}
            },
            "input_audio_buffer.committed": {
                "type": "input_audio_buffer.committed"
            },
            "conversation.item.created": {
                "type": "conversation.item.created",
                "item": {"id": "item_123"}
            }
        }
        return responses.get(response_type, {"type": response_type})

    return _response


@pytest.fixture
def mock_pyaudio_stream():
    """Mock PyAudio stream for testing audio capture"""
    stream = Mock()
    stream.read = Mock(return_value=b'\x00' * 1920)  # 20ms at 48kHz
    stream.stop_stream = Mock()
    stream.close = Mock()
    return stream


@pytest.fixture
def event_loop():
    """Create an event loop for async tests"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def spacebar_event():
    """Mock spacebar keyboard event"""
    def _event(key_down=True):
        return {
            "key": "space",
            "keyCode": 32,
            "type": "keydown" if key_down else "keyup",
            "timestamp": 1234567890
        }
    return _event


@pytest.fixture
def mock_websocket_manager():
    """Mock WebSocketManager for testing"""
    manager = AsyncMock()
    manager.broadcast_status = AsyncMock()
    manager.broadcast_transcript = AsyncMock()
    manager.broadcast_response = AsyncMock()
    manager.broadcast_api_call_count = AsyncMock()
    manager.broadcast_new_response = AsyncMock()
    manager.broadcast_error = AsyncMock()
    manager.clients = set()
    return manager


# Helper functions for tests

def create_test_audio_buffer(duration_ms=100, sample_rate=48000):
    """
    Create test audio buffer

    Args:
        duration_ms: Duration in milliseconds
        sample_rate: Sample rate in Hz

    Returns:
        bytes: Audio data as 16-bit PCM
    """
    import struct
    num_samples = int(sample_rate * duration_ms / 1000)
    # Simple sine wave for testing
    import math
    frequency = 440  # A4 note
    samples = []
    for i in range(num_samples):
        sample = int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
        samples.append(sample)
    return struct.pack('<' + 'h' * num_samples, *samples)


def assert_websocket_message(mock_ws, message_type, **expected_fields):
    """
    Assert that a WebSocket message was sent with expected fields

    Args:
        mock_ws: Mock WebSocket object
        message_type: Expected message type
        **expected_fields: Expected fields in the message
    """
    # Check if send was called
    assert mock_ws.send.called, "WebSocket send was not called"

    # Get the last call
    last_call = mock_ws.send.call_args_list[-1]
    message = json.loads(last_call[0][0])

    # Check message type
    assert message.get("type") == message_type, \
        f"Expected message type '{message_type}', got '{message.get('type')}'"

    # Check expected fields
    for field, expected_value in expected_fields.items():
        actual_value = message.get(field)
        assert actual_value == expected_value, \
            f"Expected {field}='{expected_value}', got '{actual_value}'"
