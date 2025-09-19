
class WifiMode:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        print("[WifiMode] Ready")

        # Listen for QR credentials
        bus.subscribe("wifi_credentials_scanned", self.on_wifi_qr)

        # Listen for entering/exiting this mode
        bus.subscribe("enter_wifi_mode", self.enter)
        bus.subscribe("exit_wifi_mode", self.exit)

    async def enter(self, data):
        print("[WifiMode] ENTER")
        await self.bus.publish("tts", {"text": "Wi-Fi mode activated"})
        # Ask WifiService for status
        await self.bus.publish("wifi_status")
        self.state.needQR = True

    async def exit(self, data):
        print("[WifiMode] EXIT")
        await self.bus.publish("tts", {"text": "Leaving Wi-Fi mode"})
        self.state.needQR = False

    @staticmethod
    def parse_wifi_qr(qr_text: str):
        """
            Parse Wi-Fi QR code text into a dictionary.
        Example format: WIFI:S:MySSID;T:WPA;P:mypassword;H:false;;
        """
        if not qr_text.startswith("WIFI:"):
            return None

        # Remove "WIFI:" prefix and trailing ";;"
        content = qr_text[5:].rstrip(";")

        # Split into key-value pairs
        parts = content.split(";")
        data = {}
        for part in parts:
            if ":" in part:
                key, value = part.split(":", 1)
                data[key] = value

        return {
            "ssid": data.get("S"),
            "type": data.get("T", "WPA"),
            "password": data.get("P"),
            "hidden": data.get("H", "false").lower() == "true"
        }

    async def on_wifi_qr(self, data):
        qr_text = data.get("raw")
        wifi_info = self.parse_wifi_qr(qr_text)
        if not wifi_info:
            print("[WifiMode] Invalid QR")
            return

        print(f"[WifiMode] Parsed Wi-Fi → {wifi_info}")
        await self.bus.publish("wifi_connect", wifi_info)

