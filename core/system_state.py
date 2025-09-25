# core/system_state.py
class SystemState:

    # Detect if running on Pi
    def is_raspberry_pi():
        try:
            with open("/proc/cpuinfo", "r") as f:
                return "Raspberry Pi" in f.read()
        except FileNotFoundError:
            return False

    # Use MockFactory when testing off Pi
    if not is_raspberry_pi():
        from gpiozero.pins.mock import MockFactory
        Device.pin_factory = MockFactory()
        print("[ButtonHAL] Using MockFactory (not on Raspberry Pi)")
        import keyboard  # pip install keyboard
    
    def __init__(self):
        self.current_mode = "idle"
        self.primary = True
        self.education_submode = "idle"
        self.language = "en"   # default language for TTS ("en" / "fil")
        self.network_status = "Unknown"
        
        self.VOLUME_MAX = 240
        self.VOLUME_MIN = 0
        self.volume = 100

        self.VOICE_SPEED_MAX = 280
        self.VOICE_SPEED_MIN = 100
        self.voiceSpeed = 150

        self.needQR = False

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

    def volumeUp(self):
        if self.volume < self.VOLUME_MAX:            
            self.volume = self.volume + 20
            print(f"[SystemState] Volume Increased: " + str(self.volume))
        else:
            self.volume = self.VOLUME_MAX
            print(f"[SystemState] Volume Max!: " + str(self.volume))


    def volumeDown(self):
        if self.volume > self.VOLUME_MIN:
            self.volume = self.volume - 20
            print(f"[SystemState] Volume Decreased: " + str(self.volume))
        else:
            self.volume = self.VOLUME_MIN
            print(f"[SystemState] Volume Muted: " + str(self.volume))


    def voiceSpeedIncrease(self):
        if self.voiceSpeed <= 280:
            self.voicespeed = self.voiceSpeed + 10
            print("[SystemState] Increasing Voice Speed to" + str(self.voiceSpeed))
        else:
            self.voiceSpeed = self.VOICE_SPEED_MAX
            print("[SystemState] Voice Speed cannot exceed above " + str(self.VOICE_SPEED_MAX))
        
    def voiceSpeedDecrease(self):
        if self.voiceSpeed >= 100:
            self.voiceSpeed = self.voiceSpeed - 10
            print("[SystemState] Decreasing Voice Speed to " + str(self.voiceSpeed))
        else:
            self.voicespeed = self.VOICE_SPEED_MIN
            print("[SystemState] Voice Speed cannot exceed below " + str(self.VOICE_SPEED_MIN))
