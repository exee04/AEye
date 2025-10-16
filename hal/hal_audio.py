# hal/hal_audio.py
class AudioHAL:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        bus.subscribe("tts", self.speak)

    async def speak(self, data):
        lang = self.state.language
        text = data.get("text")
        print(f"[AudioHAL] ({lang}) → {text}")
