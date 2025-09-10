# modes/quiz_mode.py

class QuizMode:
    def __init__(self, bus):
        self.bus = bus
        # Listen for when StateMachine enters quiz mode
        self.bus.subscribe("enter_quiz_mode", self.on_enter)
        print("[QuizMode] Ready and waiting...")

    async def on_enter(self, data):
        print("[QuizMode] Activated! Let's start the quiz.")
