# modes/learn_mode.py

class LearnMode:
    def __init__(self, bus):
        self.bus = bus
        # Listen for when StateMachine enters learn mode
        self.bus.subscribe("enter_learn_mode", self.on_enter)
        print("[LearnMode] Ready and waiting...")

    async def on_enter(self, data):
        print("[LearnMode] Activated! Time to teach Braille.")
