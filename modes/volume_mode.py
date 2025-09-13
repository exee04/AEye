# modes/volume_mode.py
class VolumeMode:
    def __init__(self, bus):
        self.bus = bus
        bus.subscribe("enter_volume_mode", self.enter)
        bus.subscribe("exit_volume_mode", self.exit)

    async def enter(self, data):
        print("[VolumeMode] ENTER")
        await self.bus.publish("tts", {"text": "Volume Mode activated"})

    async def exit(self, data):
        print("[VolumeMode] EXIT")
