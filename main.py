import asyncio

from core.event_bus import EventBus
from core.system_state import SystemState
from core.qr_handler import QRHandler
from core.navigation_handler import NavigationHandler

from hal.hal_buttons import ButtonHAL
from hal.hal_audio import AudioHAL
from hal.hal_camera import CameraHAL


async def main(bus, state):
    print("Initializing system...")
    ButtonHAL(bus, asyncio.get_event_loop())
    AudioHAL(bus, state)
    camera = CameraHAL(bus, state, True)
    QRHandler(bus, state)
    asyncio.create_task(state.OnStartup())
    NavigationHandler(bus, state)
    

    while True:
        camera.update()
        await asyncio.sleep(0.01)

if __name__ == "__main__":
    bus = EventBus()
    state = SystemState(bus)
    asyncio.run(main(bus, state))
