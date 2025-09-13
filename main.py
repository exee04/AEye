import asyncio
from core.event_bus import EventBus
from core.state_machine import StateMachine
from hal.hal_buttons import ButtonHAL
from hal.hal_audio import AudioHAL
from modes.learn_mode import LearnMode
from modes.quiz_mode import QuizMode
from modes.scorecheck_mode import ScoreCheckMode
from modes.wifi_mode import WifiMode
from modes.battery_mode import BatteryMode
from modes.volume_mode import VolumeMode



async def main():
    loop = asyncio.get_event_loop()
    bus = EventBus()
    StateMachine(bus)

    # HALs
    ButtonHAL(bus, loop)
    AudioHAL(bus)

    # Modes
    LearnMode(bus)
    QuizMode(bus)
    ScoreCheckMode(bus)
    WifiMode(bus)
    BatteryMode(bus)
    VolumeMode(bus)



    print("[Main] System initialized. Press buttons to test.")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())

