# OpenAI Virtual Teleprompter

A desktop application that captures audio from system speakers, processes it through OpenAI's Realtime API, and displays AI-generated text responses in a transparent, always-on-top overlay window.

## Technical Stack

**Frontend:**
- Electron (desktop application framework)
- React (UI components)
- Webpack + Babel (build tooling)
- WebSocket client

**Backend:**
- Python 3.10+
- WebSocket server (websockets library)
- PyAudio (audio capture)
- OpenAI Realtime API client
- WebRTC VAD (Voice Activity Detection)

## Architecture

The application runs as two separate processes:

1. **Python Backend** (`backend/start_websocket_server.py`):
   - WebSocket server on `ws://localhost:8000`
   - Audio capture from system recording device
   - OpenAI Realtime API integration
   - Voice Activity Detection (VAD)
   - Audio buffer management

2. **Electron Frontend** (`main.js` + React components):
   - Transparent, frameless window
   - Always-on-top overlay
   - WebSocket client
   - Real-time text display
   - User controls (start/pause/opacity)

### Data Flow

```
Audio Input → PyAudio → VAD → Buffer → OpenAI API → WebSocket → Frontend Display
```

## Prerequisites

- **Python 3.10+** (recommended for dependency compatibility)
- **Node.js 14+** and npm
- **OpenAI API Key** ([get one here](https://platform.openai.com/api-keys))
- **Windows OS** (designed for Windows 11, may work on Linux/macOS)
- **VB-Audio Virtual Cable** (for routing speaker audio to recording device)

## Installation

### Backend Setup

1. **Clone the Repository**

   ```bash
   git clone https://github.com/raoulbia-ai/gpt-meeting-assistant-electron.git
   cd gpt-meeting-assistant-electron
   ```

2. **Create Python Virtual Environment**

   ```bash
   cd backend
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Linux/macOS
   ```

3. **Install Python Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   **Windows PyAudio Installation:**
   If `pip install pyaudio` fails, use the included pre-compiled wheel:
   ```bash
   pip install pyaudio-0.2.14-cp314-cp314-win_amd64.whl
   ```

4. **Set Up OpenAI API Key**

   **Method 1 (Recommended): Use .env file**
   ```bash
   cp .env.example .env
   # Edit .env and add your API key:
   # OPENAI_API_KEY=sk-your-actual-key-here
   ```

   **Method 2: Set environment variable**
   ```powershell
   # Windows PowerShell
   $env:OPENAI_API_KEY='sk-your-actual-key-here'
   ```

### Frontend Setup

1. **Install Node.js Dependencies**

   ```bash
   cd ..  # Return to project root
   npm install
   ```

2. **Build Frontend**

   ```bash
   npm run build
   ```

### Audio Device Setup (Windows)

To capture audio from speakers (e.g., from video calls), configure VB-Audio Virtual Cable:

1. Download VB-Audio Virtual Cable from https://vb-audio.com/Cable/
2. Extract ZIP and run `VBCABLE_Setup_x64.exe` as administrator
3. Restart computer
4. Open Sound Control Panel (`Win+R` → `mmsys.cpl`)
5. **Playback tab**: Set "CABLE Input" as Default Device
6. **Recording tab**: Set "CABLE Output" as Default Device
7. **Recording tab**: Right-click "CABLE Output" → Properties → Levels → Set volume to 100%
8. **Recording tab**: Right-click "CABLE Output" → Properties → Listen tab:
   - Check "Listen to this device"
   - Select your speakers from dropdown
   - Click OK

Result: System audio routes through virtual cable to the application while you still hear it through speakers.

## Running the Application

**Two terminals required:**

**Terminal 1 - Backend:**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python start_websocket_server.py
```
On first run, select audio device ("CABLE Output" if using VB-Audio Cable).

**Terminal 2 - Frontend:**
```powershell
npm start  # Builds and launches Electron app
```

**Important:** Start backend before frontend.

## Model Selection

The application supports two OpenAI Realtime API models with different pricing tiers:

| Model | Audio Input | Audio Output | Text Input | Text Output |
|-------|-------------|--------------|------------|-------------|
| **GPT-4o Realtime (Premium)** | $100/1M tokens (~$0.06/min) | $200/1M tokens (~$0.24/min) | $5/1M tokens | $20/1M tokens |
| **GPT-4o-mini Realtime (Cheaper)** | $10/1M tokens (~$0.006/min) | $20/1M tokens (~$0.024/min) | $0.60/1M tokens | $2.40/1M tokens |

**GPT-4o-mini is approximately 10x cheaper** than GPT-4o for audio processing.

### Selecting a Model

When starting the backend, you'll be prompted to select a model:

```
Available OpenAI Realtime API models:
================================================================================

1. GPT-4o Realtime (Premium)
   Audio Input:  $100/1M tokens (~$0.06/min)
   Audio Output: $200/1M tokens (~$0.24/min)
   Text Input:   $5/1M tokens
   Text Output:  $20/1M tokens

2. GPT-4o-mini Realtime (Cheaper - 10x)
   Audio Input:  $10/1M tokens (~$0.006/min)
   Audio Output: $20/1M tokens (~$0.024/min)
   Text Input:   $0.60/1M tokens
   Text Output:  $2.40/1M tokens
================================================================================

Select model (1 or 2) [default: 1]:
```

- Enter **1** for GPT-4o Realtime (premium performance)
- Enter **2** for GPT-4o-mini Realtime (cost-effective option)
- Press Enter without input to default to GPT-4o

**Model IDs:**
- GPT-4o: `gpt-4o-realtime-preview-2024-10-01`
- GPT-4o-mini: `gpt-4o-mini-realtime-preview-2024-12-17`

## Configuration

### Backend Configuration (`backend/config.py`)

```python
self.rate = 48000  # Audio sample rate (Hz)
self.frame_duration_ms = 20  # Audio frame duration (ms)
self.channels = 1  # Mono audio
self.max_api_calls = -1  # -1 = unlimited
self.cooldown_duration = 10  # Seconds
self.model_name = self.selected_model["name"]  # Selected during startup
self.api_url = f"wss://api.openai.com/v1/realtime?model={self.model_name}"  # Dynamic based on model choice
self.instructions = "..."  # OpenAI assistant instructions
self.temperature = 0.6
```

### Frontend Configuration

- **Opacity Slider:** Adjusts window transparency (0.0 - 1.0)
- **Spacebar:** Toggle pause/resume audio capture
- **Window:** Drag via top bar, resize via bottom-right corner

## Technical Details

### Audio Processing

- **Sample Rate:** 48000 Hz
- **Format:** PCM16 (16-bit signed integers)
- **Frame Duration:** 20ms
- **Encoding:** Base64 for OpenAI API transmission
- **VAD:** WebRTC Voice Activity Detection (sensitivity level 1)

### WebSocket Protocol

**Backend → Frontend Messages:**
```json
{"type": "status", "status": "listening|paused|ready", "is_listening": bool, "is_paused": bool}
{"type": "response", "data": "AI response text"}
{"type": "transcript", "delta": "partial transcription"}
{"type": "api_call_count", "count": 123}
{"type": "audio_level", "level": 0-100}
{"type": "error", "error": {"message": "...", "code": "..."}}
```

**Frontend → Backend Messages:**
```json
{"type": "control", "action": "start_listening|pause_listening|resume_listening|stop_listening"}
```

### OpenAI Realtime API

- **Endpoint:** `wss://api.openai.com/v1/realtime`
- **Model:** `gpt-4o-realtime-preview-2024-10-01`
- **Modalities:** text, audio
- **Session Duration:** Auto-reconnects every 10 minutes (15-minute OpenAI limit)
- **Voice:** alloy
- **Turn Detection:** Server-side VAD (0.5 threshold, 200ms silence duration)

### Electron Window

- **Transparent:** `true`
- **Frameless:** `true`
- **Always on Top:** `true` (floating level)
- **Skip Taskbar:** `true`
- **Resizable:** `true` (400-1600px width, 300-1200px height)

## Logging

Logs stored in `backend/logs/` directory:
- `voice_assistant.log` - Main application log
- `openai_client.log` - OpenAI API communication
- `audio_capture.log` - Audio device and capture events
- `websocket_manager.log` - WebSocket server events

Rotation: 10MB max file size, 5 backup files.

## Project Structure

```
.
├── backend/
│   ├── start_websocket_server.py   # Entry point
│   ├── config.py                   # Configuration
│   ├── voice_assistant.py          # Main orchestrator
│   ├── audio_capture.py            # PyAudio + VAD
│   ├── openai_client.py            # OpenAI API client
│   ├── websocket_manager.py        # WebSocket server
│   ├── response_processor.py       # Response handling
│   ├── common_logging.py           # Logging setup
│   ├── constants.py                # Error codes, constants
│   └── requirements.txt            # Python dependencies
├── src/
│   ├── FloatingPrompter.js         # Main React component
│   ├── FloatingPrompter.css        # Styles
│   └── renderer.js                 # React entry point
├── main.js                         # Electron main process
├── index.html                      # Electron window HTML
├── package.json                    # Node.js dependencies
├── webpack.config.js               # Webpack build config
└── .env.example                    # Environment variables template
```

## Environment and Compatibility

- **OS:** Designed for Windows 11, may work on Linux (WSL tested)
- **Audio Devices:** Supports any audio input device; automatically selects system default
- **VB-Cable:** Required for speaker audio capture (loopback audio routing)

## License

This project is licensed under the [MIT License](LICENSE).

## Acknowledgments

- **OpenAI** - Realtime API
- **Electron** - Desktop application framework
- **PyAudio** - Audio I/O library
- **WebRTC VAD** - Voice Activity Detection
- **VB-Audio** - Virtual Cable driver

---

**Note:** This is a Proof of Concept (PoC). Users may encounter bugs or issues. For questions or issues, please open a GitHub issue.
