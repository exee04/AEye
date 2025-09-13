# modes/education/education_quiz_mode.py

class EducationQuizMode:
    def __init__(self, bus):
        self.bus = bus
        bus.subscribe("enter_education_quiz_mode", self.enter)
        bus.subscribe("exit_education_quiz_mode", self.exit)

    async def enter(self, data):
        print("[EducationQuizMode] ENTER")
        await self.bus.publish("tts", {"text": "Education sub-mode: Quiz"})

    async def exit(self, data):
        print("[EducationQuizMode] EXIT")
