import asyncio
import time

class SpeechHAL:
    def __init__(self, bus):
        self.bus = bus
        self.recording = False
        self.start_time = None
        self._recording_task = None

        print("[SpeechHAL] Initialized, waiting for main button events")

        # Subscribe to button events
        bus.subscribe("button_hold", self.on_button_hold)
        bus.subscribe("button_press", self.on_button_tap)
        bus.subscribe("button_release", self.on_button_release)

    async def on_button_hold(self, data):
        """Triggered when any button is held"""
        pin = data.get("pin")
        if pin != 24:
            return
        if pin == 24 and not self.recording:  # Main button
            self.recording = True
            self.start_time = time.time()
            print("[SpeechHAL] Recording started... (DEBUG)")

            # Start background task to print "Recording..."
            self._recording_task = asyncio.create_task(self._print_recording_loop())

            # Publish recording started event
            await self.bus.publish("speech_record_start", {"pin": pin})

    async def _print_recording_loop(self):
        """Keep printing 'Recording...' while button is held"""
        while self.recording:
            print("Recording...")
            await asyncio.sleep(0.5)

    async def on_button_tap(self, data):
        """Triggered on a short tap (not hold)"""
        pin = data.get("pin")
        if pin == 24:
            print("[SpeechHAL] Main button tapped → (reserved for future quick actions)")

    async def on_button_release(self, data):
        """Triggered when button is released"""
        pin = data.get("pin")
        if pin == 24 and self.recording:
            self.recording = False
            duration = time.time() - self.start_time
            print(f"[SpeechHAL] Recording stopped. Duration: {duration:.2f}s")

            # Cancel the loop task if running
            if self._recording_task:
                self._recording_task.cancel()
                self._recording_task = None

            # Simulate creating a file
            fake_file = f"/tmp/fake_audio_{int(time.time())}.wav"
            print(f"[SpeechHAL] Fake audio file created: {fake_file}")

            # Simulate STT result
            mock_text = "this is a mock speech-to-text result"
            print(f"[SpeechHAL] Mock STT result: '{mock_text}'")

            # Publish speech result event
            await self.bus.publish("speech_result", {
                "file": fake_file,
                "text": mock_text
            })
