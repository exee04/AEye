class WifiMode:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        print("[WifiMode] Ready (listening for wifi_credentials_scanned)")

        # Listen only for relevant QR events
        self.bus.subscribe("wifi_credentials_scanned", self.on_wifi_qr)

    async def on_wifi_qr(self, data):
        qr_text = data.get("raw")
        print(f"[WifiMode] Wi-Fi QR detected → {qr_text}")

        # TODO: Parse Wi-Fi QR format (WIFI:S:<ssid>;T:<WPA/WEP>;P:<password>;H:true;;)
        # Connect logic goes here
