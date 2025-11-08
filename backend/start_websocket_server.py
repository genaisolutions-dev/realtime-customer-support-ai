import asyncio
from websocket_manager import WebSocketManager

class MockAssistant:
    def __init__(self):
        self.is_listening = False
        self.is_running = False
        self.is_paused = False

    async def start_listening(self):
        print("MockAssistant: start_listening called")
        self.is_listening = True
        self.is_running = True

    async def stop_listening(self):
        print("MockAssistant: stop_listening called")
        self.is_listening = False
        self.is_running = False

    async def pause(self):
        print("MockAssistant: pause called")
        self.is_paused = True

    async def resume(self):
        print("MockAssistant: resume called")
        self.is_paused = False

    def stop(self):
        print("MockAssistant: stop called")
        self.is_running = False

async def main():
    assistant = MockAssistant()
    websocket_manager = WebSocketManager(assistant)

    print("Starting WebSocket server...")

    # Start the WebSocket server within an asyncio event loop
    await websocket_manager.start()  # Ensure this is awaited properly
    print("WebSocket server is running.")

    # Keep the event loop running forever to accept connections
    await asyncio.Event().wait()  # This will block indefinitely, keeping the server alive

if __name__ == "__main__":
    asyncio.run(main())
