# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Real-Time Customer Support AI** - an Electron desktop application with a Python WebSocket backend that provides real-time AI assistance for customer service teams using OpenAI's Realtime API. The application captures audio from a microphone, processes it through OpenAI's API, and displays responses in a transparent, always-on-top floating window.

**Primary Use Case**: Customer service support - helping agents respond to customer inquiries with instant access to company policies, product information, and troubleshooting procedures during live customer interactions.

## Architecture

### Two-Process Architecture

The application runs as two separate processes that must both be running:

1. **Backend (Python)**: WebSocket server that manages audio capture, OpenAI API communication, and audio processing
   - Entry point: `backend/start_websocket_server.py`
   - WebSocket server on `ws://localhost:8000`
   - Handles audio device selection, VAD (Voice Activity Detection), and OpenAI Realtime API integration

2. **Frontend (Electron + React)**: Desktop UI for displaying transcriptions and controlling the application
   - Entry point: `main.js`
   - Transparent, draggable floating window
   - Connects to backend WebSocket server
   - Built React components bundled with Webpack

### Key Architecture Components

#### Backend (`backend/`)
- **`config.py`**: Configuration singleton containing OpenAI API settings, audio parameters (48000 Hz sample rate, 20ms frames), and assistant instructions
- **`voice_assistant.py`**: Main orchestrator - manages audio capture, buffer handling, and coordinates between OpenAI client and WebSocket manager
  - **Thread Safety**: Uses `asyncio.Lock` to protect audio buffer from race conditions during pause/resume operations
  - **Event-Based Pause**: Uses `asyncio.Event` for efficient pause waiting (no CPU-wasting tight loops)
  - **Cooldown Management**: Tracks and cancels cooldown tasks during pause
  - **Audio Level Throttling**: Broadcasts audio levels at 10/sec (throttled from 50/sec)
- **`audio_capture.py`**: PyAudio wrapper with WebRTC VAD for speech detection, handles device selection and audio streaming
  - **Auto-Device Selection**: Automatically selects Windows default microphone (fallback to manual selection)
  - **VAD State Reset**: Reinitializes WebRTC VAD detector on reset for consistent speech detection
- **`openai_client.py`**: Manages WebSocket connection to OpenAI Realtime API, handles session initialization and audio encoding (base64 PCM16)
  - **Session Reset Safety**: Session reset logic moved out of `send_audio()` to prevent data loss
- **`websocket_manager.py`**: WebSocket server for frontend communication, handles control messages (start/pause/resume/stop) and broadcasts status updates
  - **Complete Handler Coverage**: Supports start_listening, pause_listening, resume_listening, and stop_listening actions
  - **Consistent Status Broadcasts**: All status messages include `is_paused` field for proper state sync
  - **Error Handling**: Try/catch blocks for JSON parsing and message processing
- **`response_processor.py`**: Processes OpenAI API responses
- **`common_logging.py`**: Centralized logging setup with file rotation
- **`constants.py`**: Shared constants for status values and user-friendly error code mapping

#### Frontend (`src/`)
- **`FloatingPrompter.js`**: Main React component with draggable UI, WebSocket client, and state management
  - **useReducer Pattern**: Response state managed with reducer (eliminates stale closure bugs)
  - **No Optimistic Updates**: Waits for backend confirmation before updating `isPaused` state
  - **Error Handling**: Try/catch blocks for WebSocket send operations
  - **Audio Level Meter**: Real-time microphone level visualization (0-100 scale, color-coded)
- **`renderer.js`**: React DOM entry point
- **`FloatingPrompter.css`**: Styles for transparent overlay UI

#### Build System
- **Webpack**: Bundles React components (`webpack.config.js`)
- **Babel**: Transpiles JSX and modern JS
- **electron-builder**: Creates distributable packages (configured in `package.json`)

## Code Review Fixes (January 2025)

A comprehensive code review identified and fixed **35 issues** across critical, medium, and minor severity levels. All fixes have been implemented and tested.

### Critical Fixes

#### Backend State & Threading
1. **Audio Buffer Race Condition Protection** (`voice_assistant.py:29`)
   - Added `asyncio.Lock()` to protect audio buffer from concurrent access
   - Prevents data corruption when pause() is called during audio processing
   - All buffer operations wrapped in `async with self.buffer_lock:`

2. **WebSocket Message Handler Coverage** (`websocket_manager.py:54-56`)
   - Added missing `stop_listening` handler
   - Added try/catch blocks for JSON parsing and message processing
   - Handles invalid messages gracefully with error broadcasts

3. **Status Broadcast Consistency** (`websocket_manager.py:21-26, 62-69`)
   - ALL status broadcasts now include `is_paused` field
   - Initial connection message includes both `is_listening` and `is_paused`
   - Frontend always receives complete state information

4. **Session Reset Timing** (`openai_client.py:66-68`)
   - Moved session reset logic OUT of `send_audio()` method
   - Prevents audio buffer loss during reset
   - Session reset now handled by main loop after operation completes

#### Frontend State Management
5. **useReducer Pattern for Response Display** (`FloatingPrompter.js:215-244`)
   - Refactored from `useState` to `useReducer` for response state
   - Eliminates stale closure bugs that caused lost text
   - Actions: `ADD_DELTA`, `COMPLETE_RESPONSE`, `NEW_RESPONSE`, `CLEAR_ALL`

6. **Removed Optimistic State Updates** (`FloatingPrompter.js:439-443`)
   - Frontend no longer updates `isPaused` before backend confirmation
   - Waits for status broadcast from backend to update UI
   - Prevents frontend-backend state desync

7. **WebSocket Send Error Handling** (`FloatingPrompter.js:292-298`)
   - Added try/catch around `ws.send()` calls
   - Catches serialization errors and network failures
   - Displays user-friendly error messages

### Medium Priority Fixes

#### VAD & Audio Processing
8. **VAD State Reinitialization** (`audio_capture.py:194-199`)
   - `reset_vad()` now reinitializes WebRTC VAD detector: `self.vad = webrtcvad.Vad(1)`
   - Ensures consistent speech detection after pause/resume
   - Removed duplicate `reset_vad()` method (line 222)

9. **Cooldown Task Management** (`voice_assistant.py:40, 51-55, 209`)
   - Cooldown tasks now tracked in `self.cooldown_task`
   - Tasks cancelled during pause to prevent stale cooldowns
   - Clean task lifecycle management

10. **Event-Based Pause Waiting** (`voice_assistant.py:28-29, 52, 78, 132-136`)
    - Replaced tight `await asyncio.sleep(0.01)` loop with `asyncio.Event`
    - Reduces CPU usage from 100 iterations/sec to near-zero when paused
    - `resume_event.wait()` blocks efficiently until resume

11. **Audio Level Broadcast Throttling** (`voice_assistant.py:31, 143-148`)
    - Throttled from 50/sec to 10/sec (100ms intervals)
    - Reduces WebSocket bandwidth usage
    - Frontend can't process faster updates anyway

12. **User-Friendly Error Codes** (`constants.py`, `voice_assistant.py:12, 243, 303`)
    - Created `constants.py` with error code mapping
    - Maps exception types to user-friendly codes: `device_error`, `connection_lost`, `timeout`, etc.
    - `get_error_code()` function used in all error broadcasts

13. **Buffer Cleanup in stop_listening()** (`voice_assistant.py:356-358`)
    - Clears `audio_buffer` and resets `buffer_ready` event
    - Prevents stale audio data from previous session

### Minor Code Quality Fixes

14. **Removed Duplicate Imports** (`audio_capture.py:1, 10-11`)
    - Removed duplicate `from pydub import AudioSegment` and `import io`

15. **Removed Unused Parameters** (`audio_capture.py:13`, `openai_client.py:9`)
    - Removed unused `debug_to_console` parameter from constructors

16. **Removed Commented Code** (`audio_capture.py:32`)
    - Removed commented `# self.setup_logging(debug_to_console)` line

### Auto-Pause Behavior

**Note**: The auto-pause behavior after sending audio to API (line 239 in `voice_assistant.py`) has been **kept as-is** per design decision. This is intentional behavior where:
1. User starts listening
2. Audio buffer fills and sends to API
3. Backend automatically pauses
4. User sees response
5. User manually resumes when ready

This prevents the system from capturing audio during AI response playback.

### Error Code Reference

The following user-friendly error codes are now used throughout the application:

| Exception Type | Error Code | User Message Context |
|---|---|---|
| `OSError`, `IOError` | `device_error` | Audio device not found or disconnected |
| `ConnectionClosed` | `connection_lost` | WebSocket connection to backend/OpenAI lost |
| `TimeoutError` | `timeout` | Operation timed out |
| `JSONDecodeError` | `invalid_json` | Malformed message received |
| `KeyError` | `missing_field` | Required field missing in message |
| `ValueError` | `invalid_value` | Invalid value provided |
| `SessionExpired` | `session_expired` | OpenAI session expired (auto-reconnects) |
| `InvalidAPIKey` | `invalid_api_key` | OpenAI API key invalid or missing |
| Unknown | `unknown_error` | Unexpected error occurred |

### Testing

All fixes have comprehensive test coverage:
- `tests/test_buffer_race_conditions.py` - Buffer lock and race condition tests
- `tests/test_state_synchronization.py` - State sync and error code tests
- `tests/test_openai_connection.py` - Connection health, throttling, and VAD tests

Run tests:
```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
pytest ../tests/ -v
```

## Development Commands

### Starting the Application (Development)

**You must run both processes in separate terminals:**

```bash
# Terminal 1 - Start Backend
cd backend
python start_websocket_server.py
# Note: On first run, you'll be prompted to select audio device

# Terminal 2 - Start Frontend (from project root)
npm start
# This runs: npm run build && electron .
```

**Important**: The backend must be running BEFORE starting the frontend, as the frontend attempts to connect to `ws://localhost:8000` on startup.

### Building for Distribution

```bash
# Build for current OS
./utils/build.sh

# Force build for specific platform
./utils/build.sh --linux

# Output: distributable files in dist/ directory
```

### Testing

```bash
# Run pytest tests for push-to-talk functionality
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
pytest ../tests/test_push_to_talk.py -v

# Run specific test class
pytest ../tests/test_push_to_talk.py::TestPushToTalkWorkflow -v

# With coverage
pytest ../tests/test_push_to_talk.py --cov=backend --cov-report=html
```

### Frontend Build Only

```bash
npm run build  # Webpack bundles src/ to dist/bundle.js
npm run electron  # Run Electron without rebuilding
```

### Utility Scripts

```bash
# Kill processes on ports 8000 and 3000
python utils/kill_ports.py
```

## Important Implementation Details

### Audio Configuration
- **Sample Rate**: 48000 Hz (configured in `config.py:11`)
- **Frame Duration**: 20ms (configured in `config.py:12`)
- **Audio Format**: PCM16 (16-bit signed integers)
- **Channels**: 1 (mono)
- **Device Selection**: Automatic - uses Windows default microphone (fallback to manual selection if no default found)
- **Supported Devices**: Any audio input device (laptop built-in, monitor built-in, webcam, USB microphones, etc.)

### OpenAI Realtime API
- **WebSocket URL**: `wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01`
- **Session Configuration** (`openai_client.py:33-51`):
  - Modalities: `["text", "audio"]`
  - Turn detection: Server-side VAD with 0.5 threshold, 200ms silence duration
  - Voice: "alloy"
  - Temperature: 0.6
- **Session Reset**: Automatically reconnects every 10 minutes to bypass OpenAI's 15-minute limitation (`openai_client.py:62`)

### WebSocket Communication Protocol

**Backend → Frontend Messages**:
```json
{"type": "status", "status": "listening|paused|ready", "is_listening": bool, "is_paused": bool}
{"type": "response", "data": "AI response text"}
{"type": "transcript", "delta": "partial transcription"}
{"type": "api_call_count", "count": 123}
{"type": "audio_level", "level": 0-100}
{"type": "error", "error": {"message": "...", "code": "..."}}
```

**Frontend → Backend Messages**:
```json
{"type": "control", "action": "start_listening|pause|resume|pause_listening|resume_listening"}
```

### Audio Processing Pipeline

1. **Capture**: PyAudio reads audio chunks (960 frames at 48kHz = 20ms)
2. **VAD**: WebRTC VAD detects speech vs silence (`audio_capture.py`)
3. **Buffer**: Audio accumulates in `voice_assistant.audio_buffer` until speech detection threshold met
4. **Send**: Buffer sent to OpenAI API when speech detected or pause triggered
5. **Response**: OpenAI response broadcast to frontend via WebSocket

### State Management

The `VoiceAssistant` class tracks multiple states:
- `is_running`: Overall assistant state
- `is_paused`: User-initiated pause (spacebar)
- `waiting_for_response`: Awaiting OpenAI response
- `cooldown_active`: Post-response cooldown period
- `is_idle`: Computed property - ready for session reset if idle

### Electron Window Configuration

The main window (`main.js`) is configured as:
- Transparent background (`transparent: true`)
- Frameless (`frame: false`)
- Always on top (`setAlwaysOnTop(true, 'floating')`)
- Hidden from taskbar (`setSkipTaskbar(true)`)
- Context isolation enabled for security

## Environment Setup

### Backend Requirements
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Windows PyAudio Installation**: If `pip install pyaudio` fails, use the pre-compiled wheel in `backend/pyaudio-0.2.14-cp314-cp314-win_amd64.whl` or download from [Unofficial Windows Binaries](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio).

### Frontend Requirements
```bash
npm install
```

### Environment Variables
```bash
# Required: OpenAI API key
export OPENAI_API_KEY='sk-...'  # Linux/macOS
set OPENAI_API_KEY='sk-...'     # Windows
```

## Troubleshooting

### Common Backend Setup Issues

#### Python Version Compatibility
- **Issue**: PyAudio wheel compatibility issues with Python 3.14+
- **Solution**: Use Python 3.10 for better package compatibility
  ```bash
  # Install Python 3.10 if needed
  python3.10 -m venv venv
  source venv/bin/activate
  ```

#### SSL Certificate Issues During pip Install
- **Issue**: SSL certificate verification failures when installing packages
- **Solution**: Use trusted-host flags:
  ```bash
  pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
  ```

#### Missing MockAssistant Attributes
- **Issue**: `backend/start_websocket_server.py` uses `MockAssistant` that may be missing required attributes
- **Solution**: Ensure `MockAssistant` class includes all required attributes:
  - `is_listening`
  - `is_running`
  - `is_paused`
  - Methods: `start_listening()`, `stop_listening()`, `pause()`, `resume()`, `stop()`

#### Package Version Issues
- **numpy**: Must specify version `>=1.26.0` for Python 3.10+ compatibility
- **websockets**: Pin to `==10.4` for stability with OpenAI Realtime API
- **pyaudio**: Use version `>=0.2.11` or pre-compiled wheel for Windows

#### Backend Server Not Starting
- **Check**: Port 8000 is not in use: `python utils/kill_ports.py`
- **Check**: Virtual environment activated
- **Check**: All dependencies installed: `pip list | grep -E "websockets|pyaudio|numpy"`
- **Check**: `OPENAI_API_KEY` environment variable is set

### Frontend Issues

#### Electron Window Not Appearing
- **Check**: Backend WebSocket server is running on `ws://localhost:8000`
- **Check**: Webpack build completed: verify `dist/bundle.js` exists
- **Check**: Console for connection errors (uncomment DevTools in `main.js:24`)

#### WebSocket Connection Failures
- **Issue**: Frontend cannot connect to backend
- **Solution**: Ensure backend started first, check firewall settings, verify WebSocket URL in `FloatingPrompter.js:6` is `ws://localhost:8000`

## File Modifications - Never Create Copies

**CRITICAL**: When updating or modifying files, ALWAYS use the original file. Never create backup copies or duplicate files.

## Common Workflows

### Adding New Control Actions

1. Add handler in `websocket_manager.py:process_message()` for new action type
2. Add corresponding method in `voice_assistant.py`
3. Update frontend `FloatingPrompter.js` to send new control message
4. Update WebSocket protocol documentation in this file

### Modifying OpenAI Session Configuration

Edit `openai_client.py:initialize_session()` - the session configuration includes:
- `modalities`: Response types (text/audio)
- `instructions`: System prompt for AI assistant
- `turn_detection`: VAD configuration for detecting when user stops speaking

### Changing Audio Device

The application automatically uses the Windows default microphone on startup. To change:
1. Set a different device as your Windows default microphone in system settings, OR
2. If auto-selection fails, the backend will prompt for manual device selection in the console
3. Device selection happens each time the backend starts (no persistence yet)

### Audio Level Meter

The frontend displays a real-time audio level meter when listening is active:
- **Location**: Appears below "Start Listening" button (only visible when listening)
- **Update Rate**: Real-time updates as audio is captured (~20ms intervals)
- **Value Range**: 0-100 representing microphone input level
- **Color Coding**:
  - Green (>70%): Strong audio signal
  - Yellow (30-70%): Moderate audio signal
  - Gray (<30%): Weak audio signal
- **Implementation**: Backend calculates RMS volume (`audio_capture.py:get_audio_level()`) and broadcasts via WebSocket

### Adjusting Speech Detection Sensitivity

Edit `audio_capture.py:31`:
```python
self.speech_frames_threshold = int(0.1 * frames_per_second)  # Currently 0.1s
```
Lower values = more sensitive (detects shorter speech), higher values = less sensitive.

## Testing Strategy

The `tests/` directory contains a TDD test suite for refactoring the application from continuous listening to push-to-talk mode. See `tests/README_TESTS.md` for:
- Test structure and categories
- TDD workflow (Red → Green → Refactor)
- Mock objects and fixtures
- Expected test results before/after refactoring

## Known Limitations

- **Dual Microphone Setup**: For virtual meetings, you need TWO microphones:
  1. High-quality mic (e.g., Blue Yeti) for the teleprompter
  2. Separate mic (e.g., webcam mic) for meeting audio
- **Platform Support**: Designed for Windows and Linux (macOS untested but should work)
- **Session Timeout**: OpenAI limits sessions to 15 minutes; app auto-reconnects at 10 minutes
- **Proof of Concept**: Expect potential bugs and issues

## SSH Usage

When using SSH commands, always use the `-q` flag for quiet mode.

## Assistant Instructions Configuration

The AI assistant instructions are configured in `config.py` (lines 48-52):
```python
base_instructions = """You are a helpful AI assistant supporting customer service agents in real-time.
                      Your role is to provide quick, accurate information to help agents respond to customer inquiries.
                      Provide concise and direct answers. Present responses as bullet points.
                      No markdown. Avoid unnecessary elaboration unless specifically requested.
                      Focus on actionable information that agents can communicate to customers immediately."""
```

Context is then appended from optional files provided at startup (company policies, product catalogs, etc.). Modify the base instructions to change the assistant's behavior and response style.
