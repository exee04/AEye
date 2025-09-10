# main.py
import asyncio
from core.event_bus import EventBus
from hal.hal_buttons import ButtonHAL
from core.state_machine import StateMachine
from modes.learn_mode import LearnMode
from modes.quiz_mode import QuizMode

async def main():
    print("[MAIN] Starting system...")

    bus = EventBus()
    loop = asyncio.get_running_loop()

    # Hardware abstraction layer
    button_hal = ButtonHAL(bus, loop)

    # State machine
    sm = StateMachine(bus)

    # Modes
    learn_mode = LearnMode(bus)
    quiz_mode = QuizMode(bus)

    print("[MAIN] System ready. Press GPIO 17 for Learn, 27 for Quiz, 23 to return Idle.")

    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
