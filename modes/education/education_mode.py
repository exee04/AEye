# modes/education/education_mode.py

class EducationMode:
    def __init__(self, bus):
        self.bus = bus
        bus.subscribe("enter_education_mode", self.enter)
        bus.subscribe("exit_education_mode", self.exit)

    async def enter(self, data):
        print("[EducationMode] ENTER")
        await self.bus.publish("tts", {"text": "Education Mode activated"})
        await self.bus.publish("education_mode_entered", {"mode": "education"})

    async def exit(self, data):
        print("[EducationMode] EXIT")
        await self.bus.publish("tts", {"text": "Leaving Education Mode"})
        await self.bus.publish("education_mode_exited", {"mode": "education"})
