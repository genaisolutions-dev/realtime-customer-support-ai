import os
import pyaudio

class Config:
    # Available OpenAI Realtime models with pricing information
    MODELS = {
        "1": {
            "name": "gpt-4o-realtime-preview-2024-10-01",
            "display_name": "GPT-4o Realtime (Premium)",
            "audio_input_price": "$100/1M tokens (~$0.06/min)",
            "audio_output_price": "$200/1M tokens (~$0.24/min)",
            "text_input_price": "$5/1M tokens",
            "text_output_price": "$20/1M tokens"
        },
        "2": {
            "name": "gpt-4o-mini-realtime-preview-2024-12-17",
            "display_name": "GPT-4o-mini Realtime (Cheaper - 10x)",
            "audio_input_price": "$10/1M tokens (~$0.006/min)",
            "audio_output_price": "$20/1M tokens (~$0.024/min)",
            "text_input_price": "$0.60/1M tokens",
            "text_output_price": "$2.40/1M tokens"
        }
    }

    def __init__(self, model_choice="1", background_context="", task_context=""):
        self.max_api_calls = -1  # Set from environment or parameters
        self.silence_threshold = 5
        self.cooldown_duration = 10
        self.min_buffer_size = 16000  # Reduced from 32000 (~166ms @ 48kHz, was 333ms)
        self.max_buffer_wait_time = 1
        self.rate = 48000  # Keep sample rate at 48000 Hz
        self.frame_duration_ms = 20  # Reduced from 30 ms
        self.channels = 1
        self.format = pyaudio.paInt16
        self.sample_width = pyaudio.get_sample_size(self.format)
        self.chunk = int(self.rate * self.frame_duration_ms / 1000)

        # Removed websocket_host and websocket_port as they are hardcoded in websocket_manager.py
        self.speaker_device_index = None
        self.api_key = os.getenv("OPENAI_API_KEY")

        # Model selection
        self.selected_model = self.MODELS.get(model_choice, self.MODELS["1"])
        self.model_name = self.selected_model["name"]
        self.api_url = f"wss://api.openai.com/v1/realtime?model={self.model_name}"

        # Build base instructions
        base_instructions = """You are a helpful AI assistant supporting customer service agents in real-time.
                              Your role is to provide quick, accurate information to help agents respond to customer inquiries.
                              Provide concise and direct answers. Present responses as bullet points.
                              No markdown. Avoid unnecessary elaboration unless specifically requested.
                              Focus on actionable information that agents can communicate to customers immediately."""

        # Append background context if provided
        if background_context.strip():
            base_instructions += f"\n\nBACKGROUND CONTEXT:\n{background_context.strip()}"

        # Append task context if provided
        if task_context.strip():
            base_instructions += f"\n\nCURRENT TASK/OBJECTIVE:\n{task_context.strip()}"

        self.instructions = base_instructions
        self.voice = "alloy"
        self.temperature = 0.6
        self.question_starters = ['what', 'when', 'where', 'who', 'why', 'how', 'can', 'could', 'would', 'will', 'do', 'does', 'is', 'are']
