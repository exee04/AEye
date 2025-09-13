# modes/wifi_mode.py
class WifiMode:
    def __init__(self, bus):
        self.bus = bus
        bus.subscribe("enter_wifi_mode", self.enter)
        bus.subscribe("exit_wifi_mode", self.exit)

    async def enter(self, data):
        print("[WifiMode] ENTER")
        await self.bus.publish("tts", {"text": "Wi-Fi Mode activated"})

    async def exit(self, data):
        print("[WifiMode] EXIT")
