# Real-Time Customer Support AI

A desktop application that provides real-time AI assistance for customer service teams. The application captures audio from microphone input, processes it through OpenAI's Realtime API, and displays AI-generated responses in a transparent, always-on-top overlay window—visible even during Zoom calls, CRM screenshares, and fullscreen applications.

## Why This Tool?

Customer service agents face an impossible challenge: know thousands of policies, products, and procedures while maintaining perfect accuracy and empathy during live customer interactions. Traditional knowledge bases require context switching (Alt+Tab to search documentation, interrupting conversation flow). This tool eliminates that friction.

**Key Differentiators:**
- **No Context Switching**: Always-on-top overlay stays visible over all applications
- **Audio Integration**: Listens to conversations in real-time, no copy/paste needed
- **Persistent Context**: Load company policies once at startup, not re-entered per query
- **Hands-Free**: Agents keep typing in CRM while AI listens and responds
- **Cost-Effective**: ~$0.006/minute with GPT-4o-mini (10x cheaper than GPT-4o)

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
   - Audio capture from microphone
   - OpenAI Realtime API integration
   - Voice Activity Detection (VAD)
   - Audio buffer management

2. **Electron Frontend** (`main.js` + React components):
   - Transparent, frameless window
   - Always-on-top overlay (visible over fullscreen apps)
   - WebSocket client
   - Real-time text display
   - User controls (start/pause/opacity)

### Data Flow

```
Microphone → PyAudio → VAD → Buffer → OpenAI API → WebSocket → Frontend Display
```

## Key Technical Decisions

### Session-Level Context Injection

**The Problem:** Agents need instant access to company knowledge (policies, product specs, troubleshooting steps). Sending this context with every API request creates latency, costs more, and hits token limits.

**The Solution:** Load company knowledge once when the session starts. The AI "knows" your entire product catalog, FAQ database, and escalation procedures for the entire shift.

**Why it matters:** When an agent asks "What's our return policy for defective products?", the response is instant. No processing delay, no re-reading context, just immediate answers. This architecture decision alone makes the difference between a useful tool and one that disrupts workflow.

### Two-Process Architecture

Think of it like this: the backend is the engine (audio processing, AI communication), and the frontend is the dashboard (UI, controls). They run as separate processes communicating via WebSocket.

**Why this matters:** Real-time audio processing at 48kHz means handling 960 samples every 20 milliseconds. If your UI framework interferes with that timing, you get audio dropouts. Separating them keeps the audio engine running smoothly while the overlay stays responsive.

### Four Technical Challenges (and Solutions)

**1. Cost: $29/day vs. $3/day per agent**

GPT-4o costs $0.06/minute. For an 8-hour shift, that's ~$29/agent/day. GPT-4o-mini is 10x cheaper at ~$3/day.

For most queries ("What's our return policy?" "Is this item in stock?"), GPT-4o-mini performs identically. Model selection is configurable so teams can choose. Technical support might need GPT-4o's reasoning; general customer service doesn't.

**2. The 15-Minute Session Timeout**

OpenAI expires connections after 15 minutes. If you let it timeout, agents see an error mid-call.

Solution: Reconnect proactively at 10 minutes, but only when idle. The system checks: "Has it been 10 minutes? Is the agent between calls?" If yes, reconnect in the background and reload the company context. Invisible to users, no interruptions.

**3. State Synchronization**

When the UI says "listening" but the backend is paused, you've lost user trust.

Solution: No optimistic updates. The frontend waits for backend confirmation before updating any state. Adds ~100ms latency to UI updates, but eliminates every sync bug.

**4. Audio Buffer Race Conditions**

When users pause mid-audio-processing, two threads access the same buffer simultaneously—one writing, one clearing.

Solution: Lock-based protection (`asyncio.Lock`). Simple, but the difference between corrupted audio and clean data.

## Prerequisites

- **Python 3.10+** (recommended for dependency compatibility)
- **Node.js 14+** and npm
- **OpenAI API Key** ([get one here](https://platform.openai.com/api-keys))
- **Windows OS** (designed for Windows 11, should work on Linux/macOS)
- **Microphone** (built-in laptop mic, USB microphone, or headset)

## Installation

### Backend Setup

1. **Clone the Repository**

   ```bash
   git clone https://github.com/genaisolutions-dev/realtime-customer-support-ai.git
   cd realtime-customer-support-ai
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
   # From project root
   npm install
   ```

2. **Build Frontend Assets**

   ```bash
   npm run build
   ```

### Audio Device Setup (Windows)

On first run, the backend will automatically select your Windows default microphone. If no default is set, you'll be prompted to choose from available devices.

**To change your default microphone:**
1. Right-click the speaker icon in the Windows taskbar
2. Select "Sound settings"
3. Under "Input", choose your preferred microphone
4. Restart the backend to apply changes

## Running the Application

**You must run both backend and frontend in separate terminals:**

### Terminal 1: Start Backend

```bash
cd backend
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS
python start_websocket_server.py
```

**On first run**, you'll be prompted to:
1. Select OpenAI model (GPT-4o or GPT-4o-mini)
2. Optionally provide context files (company policies, product catalog, etc.)

### Terminal 2: Start Frontend

```bash
# From project root
npm start
```

The transparent overlay window will appear. Click "Start Listening" to begin capturing audio.

**Important**: Backend must be running BEFORE starting frontend.

## Model Selection

The application supports two OpenAI Realtime API models with different pricing tiers:

| Model | Audio Input | Audio Output | Text Input | Text Output | Use Case |
|-------|-------------|--------------|------------|-------------|----------|
| **GPT-4o Realtime** | ~$0.06/min | ~$0.24/min | $5/1M tokens | $20/1M tokens | Complex queries, nuanced responses |
| **GPT-4o-mini Realtime** | ~$0.006/min | ~$0.024/min | $0.60/1M tokens | $2.40/1M tokens | Most customer service use cases |

**GPT-4o-mini is approximately 10x cheaper** and sufficient for most customer service scenarios. GPT-4o provides better reasoning for complex technical support or high-stakes interactions.

### Selecting a Model

When the backend starts, you'll see:

```
Select OpenAI Realtime Model:

1. GPT-4o Realtime (Premium)
   Audio: ~$0.06/min input, ~$0.24/min output
   Text: $5/1M input, $20/1M output

2. GPT-4o-mini Realtime (Cheaper - 10x)
   Audio: ~$0.006/min input, ~$0.024/min output
   Text: $0.60/1M input, $2.40/1M output

Enter choice (1 or 2):
```

**Recommendation**: Start with GPT-4o-mini. Upgrade to GPT-4o only if you need more sophisticated reasoning.

**Cost Estimation** (1-hour customer service shift, GPT-4o-mini):
- Audio processing: ~$0.36/hour
- Text responses: Negligible for typical conversations
- **Total**: ~$0.40/hour per agent

## Optional: Providing Context

The application's power comes from **context engineering** - loading your company's knowledge base at startup so the AI can provide domain-specific assistance.

### Background Context

**What it is**: Core company knowledge that rarely changes.

**Examples**:
- Company policies (return policy, warranty terms, privacy policy)
- Product catalog (features, specifications, pricing)
- FAQs (frequently asked questions and approved answers)
- Troubleshooting guides (common issues and solutions)
- Service procedures (how to process returns, refunds, escalations)

### Task Context

**What it is**: Current operational information and procedures.

**Examples**:
- Escalation procedures (when to transfer to supervisor, technical team)
- Known issues (current outages, shipping delays, product defects)
- Active promotions (discount codes, seasonal offers)
- SLA requirements (response time targets, resolution expectations)
- Compliance guidelines (GDPR, HIPAA, industry-specific regulations)

### How to Provide Context

When the backend starts, you'll be prompted:

```
OPTIONAL: Provide context to improve AI responses
================================================================================

Background Context: Company knowledge base, policies, and product information.
Examples: company policies, product catalog, FAQs, troubleshooting guides, service procedures

Provide the full path to your file:
  Windows: C:\Users\name\Documents\company_policies.md
  Linux/Mac: /home/name/documents/company_policies.md
  Relative: ./company_policies.md
To skip: press Enter

Enter file path (or press Enter to skip):
```

**Best Practices**:
- Use Markdown (.md) or plain text (.txt) files
- Organize content with clear headings and bullet points
- Keep each file focused (separate policies from product info)
- Update files when policies change, restart backend to reload

**Example File Structure**:
```
customer-service-docs/
├── company_policies.md        # Return policy, warranty, privacy
├── product_catalog.md          # Product features, specs, pricing
├── troubleshooting_guide.md    # Common issues and solutions
└── escalation_procedures.md    # When and how to escalate
```

### Notes

- Context is loaded once at startup and persists for the entire session
- Both context files are optional (press Enter to skip)
- Files are injected directly into the AI's system prompt
- No size limit, but keep content focused (AI performs better with concise, well-organized information)

## Configuration

### Backend Configuration (`backend/config.py`)

**Audio Settings**:
- Sample rate: 48000 Hz
- Frame duration: 20ms
- Format: PCM16 mono audio

**OpenAI API Settings**:
- Model: Selected at startup (GPT-4o or GPT-4o-mini)
- Voice: "alloy"
- Temperature: 0.6
- Turn detection: Server-side VAD (threshold 0.5, silence 200ms)

**Session Management**:
- Auto-reconnect every 10 minutes (bypasses OpenAI's 15-minute session limit)

### Frontend Configuration

The Electron window is configured for customer service workflows:
- **Always-on-top**: Uses `'screen-saver'` level (highest priority, visible over fullscreen apps)
- **Transparent background**: Overlays on top of CRM, Zoom, screenshares
- **Frameless**: No title bar (minimalist design)
- **Draggable**: Click and drag header to reposition

### Customizing Assistant Instructions

Default instructions are optimized for customer service in `backend/config.py` (lines 48-52):

```python
base_instructions = """You are a helpful AI assistant supporting customer service agents in real-time.
                      Your role is to provide quick, accurate information to help agents respond to customer inquiries.
                      Provide concise and direct answers. Present responses as bullet points.
                      No markdown. Avoid unnecessary elaboration unless specifically requested.
                      Focus on actionable information that agents can communicate to customers immediately."""
```

**To customize**:
1. Edit `backend/config.py`
2. Modify the `base_instructions` string
3. Restart the backend

**Customization ideas**:
- Add brand voice guidelines ("Always use positive, empathetic language")
- Specify compliance requirements ("Include GDPR disclaimer for EU customers")
- Add escalation triggers ("Suggest supervisor transfer if customer mentions 'lawyer' or 'lawsuit'")

## Technical Details

### Audio Processing

- **PyAudio** captures microphone input at 48kHz sample rate
- **WebRTC VAD** detects speech vs. silence with configurable sensitivity
- Audio accumulates in a buffer until speech is detected
- Buffer sent to OpenAI API when pause button pressed or speech threshold met
- Responses broadcast to frontend via WebSocket

**Sensitivity Tuning** (`backend/audio_capture.py:31`):
```python
self.speech_frames_threshold = int(0.1 * frames_per_second)  # 0.1 second
```
Lower = more sensitive (captures shorter speech), higher = less sensitive.

### WebSocket Protocol

**Backend → Frontend Messages**:
```json
{"type": "status", "status": "listening|paused|ready", "is_listening": bool, "is_paused": bool}
{"type": "response", "data": "AI response text"}
{"type": "transcript", "delta": "partial transcription"}
{"type": "api_call_count", "count": 123}
{"type": "audio_level", "level": 0-100}
{"type": "error", "error": {"message": "...", "code": "device_error|connection_lost|timeout"}}
```

**Frontend → Backend Messages**:
```json
{"type": "control", "action": "start_listening|pause_listening|resume_listening|stop_listening"}
```

### OpenAI Realtime API

**WebSocket URL**:
```
wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01
```
(Model name changes based on selection at startup)

**Session Configuration**:
- Modalities: `["text", "audio"]`
- Turn detection: Server-side VAD (0.5 threshold, 200ms silence)
- Instructions: Base instructions + optional context files (appended at session initialization)

**Key Insight**: Session configuration is sent ONCE when WebSocket connects. Context files are injected at this point, meaning zero latency for domain-specific knowledge during conversations.

### Electron Window

**Always-on-Top Configuration** (`main.js:37`):
```javascript
win.setAlwaysOnTop(true, 'screen-saver')
```

The `'screen-saver'` level is the highest window priority in Electron, ensuring the overlay remains visible even when customers screenshare their desktop or during fullscreen Zoom calls.

## Logging

**Backend Logs**:
- Location: `backend/logs/`
- Files: `voice_assistant.log`, `audio_capture.log`, `openai_client.log`, etc.
- Rotation: Daily, 7-day retention

**Log Levels**:
- INFO: Normal operations (session start, audio buffer status)
- WARNING: Recoverable issues (connection drops, retries)
- ERROR: Failures (audio device not found, API errors)

**To view logs**:
```bash
tail -f backend/logs/voice_assistant.log
```

## Project Structure

```
realtime-customer-support-ai/
├── backend/
│   ├── start_websocket_server.py   # Backend entry point
│   ├── config.py                   # Configuration (API keys, instructions)
│   ├── voice_assistant.py          # Main orchestrator
│   ├── audio_capture.py            # PyAudio + VAD
│   ├── openai_client.py            # OpenAI API client
│   ├── websocket_manager.py        # WebSocket server
│   ├── response_processor.py       # Response handling
│   ├── constants.py                # Error codes, status values
│   ├── common_logging.py           # Logging setup
│   └── requirements.txt            # Python dependencies
├── src/
│   ├── FloatingPrompter.js         # Main React component
│   ├── FloatingPrompter.css        # Styles
│   └── renderer.js                 # React entry point
├── main.js                         # Electron main process
├── package.json                    # Node.js dependencies
├── webpack.config.js               # Build configuration
├── tests/                          # Test suite
│   ├── test_push_to_talk.py
│   ├── test_buffer_race_conditions.py
│   ├── test_state_synchronization.py
│   └── README_TESTS.md
└── README.md                       # This file
```

## Use Cases

### Technical Support (SaaS)
Load product documentation, API reference, known bugs, troubleshooting steps. AI provides exact solutions from your docs during live support calls.

### E-commerce Customer Service
Load return policy, shipping information, product catalog. AI answers "Can I return this?" with specific policy details and deadlines.

### Healthcare Patient Support
Load insurance policies, appointment procedures, privacy regulations. AI guides agents through HIPAA-compliant responses.

### Financial Services
Load account types, fee schedules, fraud procedures. AI provides accurate policy information while flagging compliance requirements.

### Telecommunications Support
Load service plans, troubleshooting guides, coverage maps. AI walks agents through modem resets, line testing, tech dispatch.

## Environment and Compatibility

**Tested on**:
- Windows 11 (WSL2 for development)
- Python 3.10, 3.11
- Node.js 14+

**Should work on**:
- Windows 10
- Linux (Ubuntu 20.04+)
- macOS (untested)

**Known Limitations**:
- Designed for agent workflows with single microphone input
- Session timeout: OpenAI limits sessions to 15 minutes (auto-reconnects at 10 minutes)
- Proof of concept: Expect bugs, edge cases

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Built with OpenAI Realtime API
- Developed using AI-assisted coding
- Open source contributions welcome

## Contributing

This is an open-source project under MIT license. Contributions are welcome!

**Areas for improvement**:
- Additional use case examples
- Better context engineering patterns
- Multi-language support
- CRM integrations
- Analytics dashboard

Fork the repo, make improvements, submit a pull request.
