class SystemState:
    def __init__(self):
        self.hasConnection = False
        self.network_name = "Unknown"
            
        self.hasAccount = False
        self.account_name = "Unknown"

        self.current_mode = "idle"
        self.education_submode = "idle"

        self.language = "en"
        self.volume = 100
        self.voiceSpeed = 100
