# core/system_state.py
class SystemState:
    def __init__(self):
        self.current_mode = "idle"
        self.primary = True
        self.education_submode = "idle"
        self.language = "en"   # default language for TTS ("en" / "fil")
        self.network_status = "Unknown"

    def switch_mode(self, new_mode: str):
        print(f"[SystemState] Mode change: {self.current_mode} → {new_mode}")
        self.current_mode = new_mode

    def toggle_layer(self):
        self.primary = not self.primary
        layer = "primary" if self.primary else "secondary"
        print(f"[SystemState] Layer switched → {layer}")

    def cycle_education_submode(self):
        sequence = ["idle", "learn", "quiz"]
        idx = sequence.index(self.education_submode)
        next_idx = (idx + 1) % len(sequence)
        new_submode = sequence[next_idx]
        print(f"[SystemState] Education submode: {self.education_submode} → {new_submode}")
        self.education_submode = new_submode

    def toggle_language(self):
        """Switch between English and Filipino"""
        self.language = "fil" if self.language == "en" else "en"
        print(f"[SystemState] Language switched → {self.language}")
