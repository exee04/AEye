# main.py
import asyncio

# Core
from core.event_bus import EventBus
from core.state_machine import StateMachine

# HALs
from hal.hal_buttons import ButtonHAL
from hal.hal_audio import AudioHAL

# Modes - Education (parent + sub-modes)
from modes.education.education_mode import EducationMode
from modes.education.education_idle_mode import EducationIdleMode
from modes.education.education_learn_mode import EducationLearnMode
from modes.education.education_quiz_mode import EducationQuizMode

# Modes - Others
from modes.scorecheck_mode import ScoreCheckMode
from modes.wifi_mode import WifiMode
from modes.volume_mode import VolumeMode


async def main():
    # Core setup
    bus = EventBus()
    StateMachine(bus)

    # HALs
    ButtonHAL(bus, asyncio.get_event_loop())
    AudioHAL(bus)

    # Modes
    # Education: parent + sub-modes
    EducationMode(bus)
    EducationIdleMode(bus)
    EducationLearnMode(bus)
    EducationQuizMode(bus)

    # Other modes
    ScoreCheckMode(bus)
    WifiMode(bus)
    VolumeMode(bus)

    print("[Main] System initialized. Press buttons to test navigation.")

    # Idle loop
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
