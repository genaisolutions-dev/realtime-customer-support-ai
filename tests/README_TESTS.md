# Test Suite for OpenAI Virtual Teleprompter

## Overview

This test suite implements Test-Driven Development (TDD) for refactoring the application from continuous listening with auto-detection to manual push-to-talk mode.

## Test Structure

```
tests/
├── conftest.py                      # Shared fixtures and test configuration
├── test_push_to_talk.py             # Core push-to-talk functionality tests
├── test_openai_connection.py        # OpenAI connection health and startup flow tests
├── test_buffer_race_conditions.py   # Audio buffer race condition protection tests
├── test_state_synchronization.py    # Frontend-backend state sync tests
├── test_audio.py                    # Existing audio device tests
└── README_TESTS.md                  # This file
```

## Running Tests

### All Tests

```cmd
cd backend
venv\Scripts\activate
pytest ../tests/ -v
```

### Individual Test Modules

```cmd
# OpenAI Connection Tests
pytest ../tests/test_openai_connection.py -v

# Push-to-Talk Tests
pytest ../tests/test_push_to_talk.py -v

# Buffer Race Condition Tests
pytest ../tests/test_buffer_race_conditions.py -v

# State Synchronization Tests
pytest ../tests/test_state_synchronization.py -v
```

### Specific Test Class

```cmd
pytest ../tests/test_push_to_talk.py::TestPushToTalkWorkflow -v
pytest ../tests/test_openai_connection.py::TestOpenAIConnectionHealth -v
```

### Single Test

```cmd
pytest ../tests/test_push_to_talk.py::TestPushToTalkWorkflow::test_spacebar_down_starts_recording -v
```

### With Coverage

```cmd
pytest ../tests/test_push_to_talk.py --cov=backend --cov-report=html
```

## Test Categories

### 0. TestOpenAIConnectionHealth (test_openai_connection.py)
Tests OpenAI API connection and startup flow:
- ✅ Backend successfully connects to OpenAI API
- ✅ Session initialization sends correct configuration
- ✅ Session.updated response is received
- ✅ Audio processing waits for is_running=True
- ✅ start_listening() sets is_running=True
- ✅ Audio processing runs after start_listening() called
- ✅ Backend ready but waiting for user interaction
- ✅ Connection error handling (invalid API key)
- ✅ Audio level broadcasts throttled to 10/sec
- ✅ VAD state properly reinitialized on reset

### 0A. TestBufferRaceConditions (test_buffer_race_conditions.py)
Tests audio buffer race condition protection:
- ✅ Buffer lock prevents concurrent access during pause
- ✅ process_audio properly uses buffer lock
- ✅ Pause during audio read is safe
- ✅ Resume event unblocks process_audio
- ✅ Cooldown task created and tracked
- ✅ Cooldown cancelled on pause

### 0B. TestStateSynchronization (test_state_synchronization.py)
Tests frontend-backend state synchronization:
- ✅ Initial status includes is_paused field
- ✅ All status broadcasts include is_paused
- ✅ Pause broadcasts correct status
- ✅ Frontend waits for backend confirmation (no optimistic updates)
- ✅ stop_listening handler exists and works
- ✅ stop_listening clears audio buffer
- ✅ Error code mapping provides user-friendly codes
- ✅ broadcast_error uses friendly error codes

### 1. TestPushToTalkWorkflow
Tests the complete push-to-talk workflow:
- ✅ Spacebar DOWN starts recording
- ✅ Spacebar UP sends audio buffer
- ✅ No auto-pause after response (ready for next input)

### 2. TestOpenAISessionConfiguration
Tests OpenAI Realtime API configuration:
- ⏭️ `turn_detection` set to `None` (manual mode)
- ⏭️ `modalities` set to `["text"]` (text-only responses)

### 3. TestVADRemoval
Tests that WebRTC VAD is removed:
- ⏭️ No `webrtcvad` import
- ⏭️ No `is_speech()` method calls
- ⏭️ Simplified audio processing loop

### 4. TestBufferManagement
Tests simplified buffer logic:
- ⏭️ Immediate send on spacebar release
- ⏭️ No threshold checks
- ⏭️ No timeout logic

### 5. TestSpacebarKeyboardControl
Tests keyboard event handling:
- ⏭️ Spacebar keydown event
- ⏭️ Spacebar keyup event
- ⏭️ WebSocket message routing

## Test Status Legend

- ✅ **Passing** - Test currently passes
- ⏭️ **Pending** - Test will fail until refactoring complete
- ⚠️ **Skipped** - Test skipped with pytest.skip()
- ❌ **Failing** - Test failing (expected during TDD red phase)

## TDD Workflow

### Phase 1: Red (Write Failing Tests)
Write tests that define the desired behavior. These tests will FAIL because the code doesn't implement the behavior yet.

```cmd
pytest ../tests/test_push_to_talk.py -v
# Expected: Multiple failures
```

### Phase 2: Green (Make Tests Pass)
Implement minimal changes to make tests pass:

1. Update `openai_client.py:initialize_session()`
   - Set `turn_detection: None`
   - Set `modalities: ["text"]`

2. Update `websocket_manager.py:process_message()`
   - Add `spacebar_down` handler
   - Add `spacebar_up` handler

3. Update `voice_assistant.py`
   - Remove auto-pause (line 210)
   - Add `start_recording()` method
   - Update `send_buffer_to_api()` to skip threshold checks

4. Run tests again:
```cmd
pytest ../tests/test_push_to_talk.py -v
# Expected: Tests start passing
```

### Phase 3: Refactor (Clean Up)
Once tests pass, refactor:

1. Remove `webrtcvad` from `requirements.txt`
2. Remove `is_speech()` from `audio_capture.py`
3. Simplify `process_audio()` loop
4. Remove unused config parameters
5. Update documentation

Run tests after each change:
```cmd
pytest ../tests/test_push_to_talk.py -v
# Should stay green during refactoring
```

## Mock Objects

### Available Fixtures

- `config` - Test configuration object
- `mock_audio_data` - Simulated audio data
- `mock_websocket` - Mock WebSocket connection
- `mock_openai_response()` - Generate mock API responses
- `mock_pyaudio_stream` - Mock audio stream
- `spacebar_event()` - Mock keyboard events
- `mock_websocket_manager` - Mock WebSocket manager

### Helper Functions

- `create_test_audio_buffer()` - Generate test audio
- `assert_websocket_message()` - Assert WebSocket message format

## Integration Tests

For integration testing with real OpenAI API:

```cmd
# Set API key
set OPENAI_API_KEY=sk-your-real-key

# Run integration tests (marked with @pytest.mark.integration)
pytest ../tests/test_push_to_talk.py -v -m integration
```

## Continuous Testing

Watch for changes and auto-run tests:

```cmd
pytest-watch ../tests/test_push_to_talk.py -v
```

## Expected Test Results (Before Refactoring)

```
test_push_to_talk.py::TestPushToTalkWorkflow::test_spacebar_down_starts_recording PASSED
test_push_to_talk.py::TestPushToTalkWorkflow::test_spacebar_up_sends_audio_buffer PASSED
test_push_to_talk.py::TestPushToTalkWorkflow::test_no_auto_pause_after_response FAILED
test_push_to_talk.py::TestOpenAISessionConfiguration::test_turn_detection_set_to_none FAILED
test_push_to_talk.py::TestOpenAISessionConfiguration::test_modalities_text_only FAILED
test_push_to_talk.py::TestVADRemoval::test_no_webrtcvad_import FAILED
test_push_to_talk.py::TestBufferManagement::test_buffer_sends_immediately_on_release PASSED
test_push_to_talk.py::TestSpacebarKeyboardControl::test_spacebar_keydown_event SKIPPED
test_push_to_talk.py::TestSpacebarKeyboardControl::test_spacebar_keyup_event SKIPPED
```

## Expected Test Results (After Refactoring)

```
All tests should PASS ✅
```

## Troubleshooting

### Import Errors
```
ModuleNotFoundError: No module named 'X'
```
**Solution:** Ensure virtual environment activated and dependencies installed:
```cmd
venv\Scripts\activate
pip install -r requirements.txt
```

### Async Test Errors
```
RuntimeError: no running event loop
```
**Solution:** Ensure test decorated with `@pytest.mark.asyncio`

### Mock Not Working
```
AttributeError: Mock object has no attribute 'X'
```
**Solution:** Use `AsyncMock` for async methods, configure return values

## Next Steps

1. ✅ Test infrastructure created
2. ⏭️ Run baseline tests (expect failures)
3. ⏭️ Implement minimal fixes (Phase 2: Green)
4. ⏭️ Refactor and clean up (Phase 3: Blue)
5. ⏭️ Validate with real interview scenario

## References

- pytest documentation: https://docs.pytest.org/
- pytest-asyncio: https://pytest-asyncio.readthedocs.io/
- unittest.mock: https://docs.python.org/3/library/unittest.mock.html
