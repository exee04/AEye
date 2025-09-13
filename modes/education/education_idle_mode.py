# modes/education/education_idle_mode.py

class EducationIdleMode:
    def __init__(self, bus):
        self.bus = bus
        bus.subscribe("enter_education_idle_mode", self.enter)
        bus.subscribe("exit_education_idle_mode", self.exit)

    async def enter(self, data):
        print("[EducationIdleMode] ENTER")
        await self.bus.publish("tts", {"text": "Education sub-mode: Idle"})

    async def exit(self, data):
        print("[EducationIdleMode] EXIT")
