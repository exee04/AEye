# main.py
import asyncio

# Core
from core.event_bus import EventBus
from core.state_machine import StateMachine
from core.system_state import SystemState

# HALs
from hal.hal_buttons import ButtonHAL
from hal.hal_audio import AudioHAL
from hal.hal_camera import CameraHAL

# Modes - Education (parent + sub-modes)
from modes.education.education_mode import EducationMode
from modes.education.education_idle_mode import EducationIdleMode
from modes.education.education_learn_mode import EducationLearnMode
from modes.education.education_quiz_mode import EducationQuizMode

# Modes - Others
from modes.scorecheck_mode import ScoreCheckMode
from modes.wifi_mode import WifiMode
from modes.volume_mode import VolumeMode


async def thermal_monitor():
    """Print CPU temperature every 10 seconds (Raspberry Pi only)."""
    while True:
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp_str = f.readline().strip()
            temp = float(temp_str) / 1000.0
            print(f"[ThermalMonitor] CPU Temperature: {temp:.1f} °C")
        except FileNotFoundError:
            # Not running on Pi → skip
            pass
        await asyncio.sleep(3) 

async def main():
    # Core setup
    print("cam test")
    bus = EventBus()
    state = SystemState()
    sm = StateMachine(bus, state)

    # HALs
    camera = CameraHAL(bus, state, show_preview=True)
    ButtonHAL(bus, asyncio.get_event_loop())
    AudioHAL(bus, state=state, i18n=None)  # Simplified, add i18n later
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
    
    asyncio.create_task(thermal_monitor())

    print("[Main] System initialized. Press buttons to test navigation.")

    # Idle loop
    while True:
        camera.update()
        await asyncio.sleep(0.01)


if __name__ == "__main__":
    asyncio.run(main())
