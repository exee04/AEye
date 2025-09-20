# modes/education/education_learn_mode.py

class EducationLearnMode:
    def __init__(self, bus):
        self.bus = bus
        self.is_active = False
        bus.subscribe("enter_education_learn_mode", self.enter)
        bus.subscribe("exit_education_learn_mode", self.exit)
        bus.subscribe("braille_letter_detected", self.on_letter_detected)

    async def enter(self, data):
        print("[EducationLearnMode] ENTER")
        self.is_active = True
        await self.bus.publish("tts", {"text": "Education sub-mode: Learn. Touch a braille letter to hear it."})
        await self.bus.publish("education_mode_entered", {"submode": "learn"})

    async def exit(self, data):
        print("[EducationLearnMode] EXIT")
        self.is_active = False
        await self.bus.publish("education_mode_exited", {"submode": "learn"})
        
    async def on_letter_detected(self, data):
        """Handle detected braille letter in learn mode"""
        if not self.is_active:
            return
            
        letter = data.get("letter", "?")
        dot_pattern = data.get("dot_pattern", "")
        
        if letter != "?":
            print(f"[EducationLearnMode] Letter detected: {letter} (pattern: {dot_pattern})")
            await self.bus.publish("tts", {"text": f"The letter is {letter}"})
        else:
            print(f"[EducationLearnMode] Unknown braille pattern detected: {dot_pattern}")
            await self.bus.publish("tts", {"text": "Unknown letter pattern detected"})
