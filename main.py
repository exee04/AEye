import asyncio

from core.event_bus import EventBus
from core.system_state import SystemState
from core.qr_handler import QRHandler
from core.navigation_handler import NavigationHandler
from core.network_handler import NetworkHandler
from core.account_handler import AccountHandler
from core.api_handler import APIHandler

from core.modes.education_mode import EducationMode

from hal.hal_buttons import ButtonHAL
from hal.hal_audio import AudioHAL
from hal.hal_camera import CameraHAL
from hal.hal_vibrate import VibrateHAL
from hal.hal_speech import SpeechHAL

async def main(bus, state):
    print("Initializing system...")
    ButtonHAL(bus, asyncio.get_event_loop())
    AudioHAL(bus, state)
    VibrateHAL(bus, state)
    SpeechHAL(bus)
    educMode = EducationMode(bus, state)
    camera = CameraHAL(bus, state, show_preview=True, edu_mode=educMode)
    await bus.publish("camera_switch_res", {"res": (1536, 864)})
    NetworkHandler(bus, state)
    APIHandler(bus, state)
    AccountHandler(bus, state)
    QRHandler(bus, state)
    asyncio.create_task(state.OnStartup())
    asyncio.create_task(state.thermal_monitor())

    # Init Modes
    NavigationHandler(bus, state)
    while True:
        await camera.update()
        await asyncio.sleep(0.15)

if __name__ == "__main__":
    bus = EventBus()
    state = SystemState(bus)
    asyncio.run(main(bus, state))
