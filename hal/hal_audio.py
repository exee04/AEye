# hal/hal_audio.py
import asyncio

class AudioHAL:
    def __init__(self, bus, i18n, state):
        self.bus = bus
        self.i18n = i18n
        self.state = state

        bus.subscribe("tts", self.speak)
        bus.subscribe("toggle_language", self.toggle_language)

    async def speak(self, data):
        key = data.get("key")
        text = data.get("text")

        if key:  # prefer key-based lookup
            text = self.i18n.t(key)

        lang = self.state.language
        print(f"[AudioHAL] ({lang}) → {text}")
        # Real TTS engine goes here

    async def toggle_language(self, _):
        self.state.language = "fil" if self.state.language == "en" else "en"
        print(f"[AudioHAL] Language toggled → {self.state.language}")
        await self.bus.publish("tts", {"key": "language_switched"})
