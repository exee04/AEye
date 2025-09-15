# core/system_state.py

class SystemState:
    def __init__(self):
        # App navigation
        self.layer = "primary"
        self.current_mode = "idle"
        self.education_submode = None

        # User preferences
        self.language = "en"   # <-- GLOBAL language variable (default English)

        # Audio
        self.volume = 5
