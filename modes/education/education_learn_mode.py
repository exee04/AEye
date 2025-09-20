# modes/education/education_learn_mode.py

class EducationLearnMode:
    def __init__(self, bus):
        self.bus = bus
        self.current_letter = None
        bus.subscribe("enter_education_learn_mode", self.enter)
        bus.subscribe("exit_education_learn_mode", self.exit)
        bus.subscribe("letter_selected", self.on_letter_selected)

    async def enter(self, data):
        print("[EducationLearnMode] ENTER")
        await self.bus.publish("tts", {"text": "Learn mode activated. Touch a braille letter to hear it."})

    async def exit(self, data):
        print("[EducationLearnMode] EXIT")
        self.current_letter = None

    async def on_letter_selected(self, data):
        """Handle when a letter is selected in learn mode"""
        if data.get("mode") == "learn":
            letter = data.get("letter")
            self.current_letter = letter
            print(f"[EducationLearnMode] Letter selected: {letter}")
            # The TTS is already handled in BrailleDetect.py
