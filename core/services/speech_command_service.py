import re


class SpeechCommandService:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state

        self.bus.subscribe("speech_result", self.on_speech_result)
        print("[SpeechCommandService] Initialized (listening for 'speech_result')")

        # Map simple phrases to states
        self.state_keywords = {
            "idle": ["idle", "home"],
            "education": ["education", "learn mode", "learning"],
            "scorecheck": ["score", "score check", "scores"],
            "wifi": ["wifi", "network"],
            "volume": ["volume", "sound"],
        }

    async def on_speech_result(self, data):
        text = (data or {}).get("text", "")
        normalized = text.strip().lower()
        if not normalized:
            print("[SpeechCommandService] Empty transcript; ignoring")
            return

        print(f"[SpeechCommandService] Heard: '{normalized}'")

        # Small talk
        if any(greet in normalized for greet in ["hello", "hi", "hey"]):
            print("[SpeechCommandService] → Hello there! 👋")
            await self.bus.publish("tts", {"text": "Hello!"})

        # Volume controls
        if any(p in normalized for p in ["volume up", "increase volume", "louder", "turn it up"]):
            print("[SpeechCommandService] → Requesting volume up")
            await self.bus.publish("request_volume_up", {})

        if any(p in normalized for p in ["volume down", "decrease volume", "quieter", "turn it down"]):
            print("[SpeechCommandService] → Requesting volume down")
            await self.bus.publish("request_volume_down", {})

        # Language toggle
        if any(p in normalized for p in ["toggle language", "switch language", "change language"]):
            print("[SpeechCommandService] → Toggling language")
            await self.bus.publish("toggle_language", {})

        # Education submodes
        if any(p in normalized for p in ["learn mode", "start learning", "learning mode"]):
            print("[SpeechCommandService] → Request education submode 'learn'")
            await self.bus.publish("request_education_submode", {"submode": "learn"})
        if any(p in normalized for p in ["quiz mode", "start quiz", "begin quiz"]):
            print("[SpeechCommandService] → Request education submode 'quiz'")
            await self.bus.publish("request_education_submode", {"submode": "quiz"})

        # Generic state switching: "go to X", "move to X", "switch to X", "open X"
        target_state = self._extract_target_state(normalized)
        if target_state:
            print(f"[SpeechCommandService] → Requesting switch to state '{target_state}'")
            await self.bus.publish("request_switch_state", {"state": target_state})

    def _extract_target_state(self, normalized_text):
        """Return a canonical state name if text contains a known target."""
        intent_patterns = [
            r"\bgo to ([a-z ]+)\b",
            r"\bmove to ([a-z ]+)\b",
            r"\bswitch to ([a-z ]+)\b",
            r"\bopen ([a-z ]+)\b",
            r"\benter ([a-z ]+)\b",
        ]

        candidates = []
        for pattern in intent_patterns:
            match = re.search(pattern, normalized_text)
            if match:
                candidates.append(match.group(1).strip())

        # Also allow bare state mentions like "education state"
        for canonical, keywords in self.state_keywords.items():
            if any(kw in normalized_text for kw in keywords + [f"{canonical} state"]):
                candidates.append(canonical)

        # Normalize candidates to canonical state
        for candidate in candidates:
            canonical = self._canonicalize_state(candidate)
            if canonical:
                return canonical
        return None

    def _canonicalize_state(self, phrase):
        phrase = phrase.strip().lower()
        # Remove trailing word 'state' if present
        if phrase.endswith(" state"):
            phrase = phrase[:-6]
        for canonical, keywords in self.state_keywords.items():
            if phrase == canonical or any(k in phrase for k in keywords):
                return canonical
        return None


