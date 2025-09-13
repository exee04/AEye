# modes/scorecheck_mode.py
class ScoreCheckMode:
    def __init__(self, bus):
        self.bus = bus
        bus.subscribe("enter_scorecheck_mode", self.enter)
        bus.subscribe("exit_scorecheck_mode", self.exit)

    async def enter(self, data):
        print("[ScoreCheckMode] ENTER")
        await self.bus.publish("tts", {"text": "Score Check Mode activated"})

    async def exit(self, data):
        print("[ScoreCheckMode] EXIT")
