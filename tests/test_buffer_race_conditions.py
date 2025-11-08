"""
Test suite for audio buffer race condition fixes

Tests the asyncio.Lock protection implemented to prevent race conditions
when pause() is called during audio processing.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch


class TestBufferLockProtection:
    """Test that buffer operations are protected by asyncio.Lock"""

    @pytest.mark.asyncio
    async def test_buffer_lock_prevents_concurrent_access(self, config, mock_websocket_manager):
        """Test that buffer lock prevents race condition during pause"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.start_stream = Mock()
            audio_capture.stop_stream = Mock()
            audio_capture.read_audio = AsyncMock(return_value=b'\x00' * 1920)
            audio_capture.get_audio_level = Mock(return_value=50)
            audio_capture.is_speech = AsyncMock(return_value=True)
            audio_capture.reset_vad = Mock()

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)
            openai_client.send_audio = AsyncMock()

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Verify buffer lock exists
        assert hasattr(assistant, 'buffer_lock')
        assert isinstance(assistant.buffer_lock, asyncio.Lock)

        # Simulate concurrent buffer access
        assistant.audio_buffer = b'test_audio_data'

        async def try_modify_buffer():
            async with assistant.buffer_lock:
                await asyncio.sleep(0.05)  # Hold lock briefly
                assistant.audio_buffer += b'_modified'

        async def try_pause():
            await asyncio.sleep(0.01)  # Start slightly after
            await assistant.pause()

        # Run concurrently
        await asyncio.gather(try_modify_buffer(), try_pause())

        # Buffer should be cleared by pause (which acquired lock after modification)
        assert assistant.audio_buffer == b''


    @pytest.mark.asyncio
    async def test_process_audio_uses_buffer_lock(self, config, mock_websocket_manager):
        """Test that process_audio properly uses buffer lock"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.read_audio = AsyncMock(return_value=b'\x00' * 1920)
            audio_capture.get_audio_level = Mock(return_value=50)
            audio_capture.is_speech = AsyncMock(return_value=True)

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        assistant.is_running = True
        assistant.min_buffer_size = 32000

        # Create task
        audio_task = asyncio.create_task(assistant.process_audio())
        await asyncio.sleep(0.1)  # Let it process some audio

        # Verify buffer accumulated (lock allowed access)
        assert len(assistant.audio_buffer) > 0

        # Clean up
        assistant.is_running = False
        assistant.resume_event.set()  # Unblock if paused
        audio_task.cancel()
        try:
            await audio_task
        except asyncio.CancelledError:
            pass


class TestPauseResumeSafety:
    """Test pause/resume operations are safe from race conditions"""

    @pytest.mark.asyncio
    async def test_pause_during_audio_read(self, config, mock_websocket_manager):
        """Test pause called during audio read doesn't cause issues"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.start_stream = Mock()
            audio_capture.stop_stream = Mock()
            # Simulate slow audio read
            async def slow_read():
                await asyncio.sleep(0.05)
                return b'\x00' * 1920
            audio_capture.read_audio = AsyncMock(side_effect=slow_read)
            audio_capture.get_audio_level = Mock(return_value=50)
            audio_capture.is_speech = AsyncMock(return_value=False)

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        assistant.is_running = True
        audio_task = asyncio.create_task(assistant.process_audio())

        # Wait for audio read to start
        await asyncio.sleep(0.01)

        # Call pause during read
        await assistant.pause()

        # Should complete without error
        assert assistant.is_paused == True

        # Clean up
        assistant.is_running = False
        assistant.resume_event.set()
        audio_task.cancel()
        try:
            await audio_task
        except asyncio.CancelledError:
            pass


    @pytest.mark.asyncio
    async def test_resume_event_unblocks_process_audio(self, config, mock_websocket_manager):
        """Test that resume event properly unblocks audio processing"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.start_stream = Mock()
            audio_capture.stop_stream = Mock()
            audio_capture.read_audio = AsyncMock(return_value=b'\x00' * 1920)
            audio_capture.get_audio_level = Mock(return_value=50)
            audio_capture.is_speech = AsyncMock(return_value=False)
            audio_capture.reset_vad = Mock()

        with patch.object(OpenAIClient, '__init__', return_value=None):
            openai_client = OpenAIClient(config)

        response_processor = ResponseProcessor(config)

        assistant = VoiceAssistant(
            config, audio_capture, openai_client,
            mock_websocket_manager, response_processor
        )

        # Verify resume event starts set
        assert assistant.resume_event.is_set() == True

        # Start processing
        assistant.is_running = True
        audio_task = asyncio.create_task(assistant.process_audio())
        await asyncio.sleep(0.05)

        # Pause - should clear event
        await assistant.pause()
        assert assistant.resume_event.is_set() == False

        # Audio processing should be blocked now
        read_count_before = audio_capture.read_audio.call_count

        await asyncio.sleep(0.05)
        read_count_after = audio_capture.read_audio.call_count

        # Should not have read more audio while paused
        assert read_count_after == read_count_before

        # Resume - should set event
        await assistant.resume()
        assert assistant.resume_event.is_set() == True

        await asyncio.sleep(0.05)
        read_count_resumed = audio_capture.read_audio.call_count

        # Should have read more audio after resume
        assert read_count_resumed > read_count_after

        # Clean up
        assistant.is_running = False
        audio_task.cancel()
        try:
            await audio_task
        except asyncio.CancelledError:
            pass


class TestCooldownTaskManagement:
    """Test cooldown task is properly managed"""

    @pytest.mark.asyncio
    async def test_cooldown_task_created_and_tracked(self, config, mock_websocket_manager):
        """Test that cooldown task is created and tracked"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

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

        # Simulate sending buffer
        assistant.audio_buffer = b'\x00' * 32000
        await assistant.send_buffer_to_api()

        # Cooldown task should be created
        assert assistant.cooldown_task is not None
        assert isinstance(assistant.cooldown_task, asyncio.Task)
        assert assistant.cooldown_active == True

        # Wait for cooldown to complete
        await asyncio.sleep(config.cooldown_duration + 0.1)
        assert assistant.cooldown_active == False


    @pytest.mark.asyncio
    async def test_cooldown_cancelled_on_pause(self, config, mock_websocket_manager):
        """Test that cooldown is cancelled when pause is called"""
        from voice_assistant import VoiceAssistant
        from audio_capture import AudioCapture
        from openai_client import OpenAIClient
        from response_processor import ResponseProcessor

        with patch.object(AudioCapture, '__init__', return_value=None):
            audio_capture = AudioCapture(config)
            audio_capture.stop_stream = Mock()
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

        # Start cooldown
        assistant.audio_buffer = b'\x00' * 32000
        await assistant.send_buffer_to_api()

        assert assistant.cooldown_active == True
        cooldown_task = assistant.cooldown_task

        # Pause should cancel cooldown
        await assistant.pause()

        assert assistant.cooldown_active == False
        assert cooldown_task.cancelled()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
