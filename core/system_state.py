import asyncio


class SystemState:
    def __init__(self, bus):
        self.bus = bus
        self.skipped_startup = False
        self.hasConnection = False
        self.network_name = "Unknown"

        self.hasAccount = False
        self.account_name = "Unknown"

        self.current_system_mode = "Initialization"
        self.current_network_state = "Unknown"

        self.language = "en"
        self.volume = 100
        self.voiceSpeed = 100
        bus.subscribe("button_press", self.SkipStartup)

    async def SkipStartup(self, data):
        if self.current_system_mode != "Initialization":
            return
        pin = data.get("pin")
        if pin != 24:
            return
        self.skipped_startup = True

    async def OnStartup(self):
        last_prompt = None
        reminder_timer = 0
        elapsed_time = 0
        timeout_seconds = 40
        reminder_interval = 15

        while not (self.hasConnection and self.hasAccount):
            # --- Abort if user forces offline mode ---
            if self.skipped_startup:
                await self.bus.publish("tts", {"text": "Starting in offline mode."})
                self.current_network_state = "OFFLINE_MODE"
                return

            # --- Timeout to offline mode ---
            if elapsed_time >= timeout_seconds:
                await self.bus.publish("tts", {"text": "No QR found. Starting in offline mode."})
                self.current_network_state = "OFFLINE_MODE"
                return

            # --- Wi-Fi Scan Phase ---
            if not self.hasConnection:
                if last_prompt != "wifi":
                    await self.bus.publish("tts", {"text": "Scan Wi-Fi QR"})
                    last_prompt = "wifi"
                    reminder_timer = 0
                reminder_timer += 1
                if reminder_timer >= reminder_interval:
                    await self.bus.publish("tts", {"text": "Still scanning for Wi-Fi."})
                    reminder_timer = 0
                await asyncio.sleep(1)
                elapsed_time += 1
                continue

            # --- Account Scan Phase ---
            if not self.hasAccount:
                if last_prompt != "account":
                    await self.bus.publish("tts", {"text": "Scan Account QR"})
                    last_prompt = "account"
                    reminder_timer = 0
                reminder_timer += 1
                if reminder_timer >= reminder_interval:
                    await self.bus.publish("tts", {"text": "Still waiting for account QR."})
                    reminder_timer = 0
                await asyncio.sleep(1)
                elapsed_time += 1
                continue

        # --- If both found ---
        if self.hasConnection and self.hasAccount:
            self.current_network_state = "ONLINE_FULL"
        elif self.hasConnection and not self.hasAccount:
            self.current_network_state = "ONLINE_NO_ACCOUNT"
        else:
            self.current_network_state = "OFFLINE_MODE"

        await self.bus.publish("tts", {"text": "Setup complete."})

