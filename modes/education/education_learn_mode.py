# modes/education/education_learn_mode.py

class EducationLearnMode:
    def __init__(self, bus):
        self.bus = bus
        bus.subscribe("enter_education_learn_mode", self.enter)
        bus.subscribe("exit_education_learn_mode", self.exit)

    async def enter(self, data):
        print("[EducationLearnMode] ENTER")
        await self.bus.publish("tts", {"text": "Education sub-mode: Learn"})

    async def exit(self, data):
        print("[EducationLearnMode] EXIT")
