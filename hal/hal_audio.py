# hal/hal_audio.py
class AudioHAL:
    def __init__(self, bus):
        bus.subscribe("tts", self.speak)

    async def speak(self, data):
        print(f"[AudioHAL] TTS → {data['text']}")
