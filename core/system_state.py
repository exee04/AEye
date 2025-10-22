import asyncio


class SystemState:
    STARTUP_TIMEOUT = 40
    REMINDER_INTERVAL = 15

    def __init__(self, bus):
        self.bus = bus

        # State variables
        self.skipped_startup = False
        self.needQR = False
        self.hasConnection = False
        self.network_status = "Unknown"
        self.hasAccount = False
        self.account_name = "Unknown"

        self.current_system_mode = "Initialization"
        self.current_network_state = "Unknown"

        # Configs
        self.language = "en"
        self.volume = 100
        self.voiceSpeed = 100

        # Subscriptions
        bus.subscribe("button_press", self.SkipStartup)
        bus.subscribe("network_status", self.OnNetworkChange)

    async def SkipStartup(self, data):
        """Allow user to skip startup via button press."""
        if self.current_system_mode != "Initialization":
            return
        pin = data.get("pin")
        if pin == 24:
            self.skipped_startup = True
            self.needQR = False

    async def OnNetworkChange(self, data):
        """React to network status changes from NetworkHandler."""
        self.hasConnection = data.get("connected", False)
        self.network_status = data.get("status", "Unknown")

    async def _scan_phase(self, prompt, check_condition, reminder_text):
        """Generalized scanning phase with reminders and timeout."""
        elapsed, reminder_timer = 0, 0
        await self.bus.publish("tts", {"text": prompt})

        while not check_condition():
            if self.skipped_startup:
                return "SKIPPED"
            if elapsed >= self.STARTUP_TIMEOUT:
                return "TIMEOUT"

            reminder_timer += 1
            if reminder_timer >= self.REMINDER_INTERVAL:
                await self.bus.publish("tts", {"text": reminder_text})
                reminder_timer = 0

            await asyncio.sleep(1)
            elapsed += 1

        return "SUCCESS"

    async def _start_offline_mode(self, reason):
        """Enter offline mode after skip or timeout."""
        msg = (
            "Starting in offline mode."
            if reason == "SKIPPED"
            else "No QR found. Starting in offline mode."
        )
        await self.bus.publish("tts", {"text": msg})
        self.current_network_state = "OFFLINE_MODE"
        self.needQR = False
        self.current_system_mode = "Idle"

    async def OnStartup(self):
        """Handles startup logic with timeout, reminders, and offline fallback."""
        self.needQR = True
        self.current_system_mode = "Initialization"

        # --- Phase 1: Wi-Fi ---
        wifi_result = await self._scan_phase(
            prompt="Scan Wi-Fi QR",
            check_condition=lambda: self.hasConnection,
            reminder_text="Still scanning for Wi-Fi.",
        )
        if wifi_result != "SUCCESS":
            return await self._start_offline_mode(wifi_result)

        # --- Phase 2: Account ---
        account_result = await self._scan_phase(
            prompt="Scan Account QR",
            check_condition=lambda: self.hasAccount,
            reminder_text="Still waiting for account QR.",
        )
        if account_result != "SUCCESS":
            return await self._start_offline_mode(account_result)

        # --- Online Mode ---
        await self.bus.publish("init_api")
        self.current_network_state = "ONLINE_FULL"
        self.current_system_mode = "Idle"
        self.needQR = False
        await self.bus.publish("tts", {"text": "Setup complete."})

    async def thermal_monitor(self):
        """Print CPU temperature every few seconds (Raspberry Pi only)."""
        while True:
            try:
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp = float(f.readline().strip()) / 1000.0
                print(f"[ThermalMonitor] CPU Temperature: {temp:.1f} °C")
            except FileNotFoundError:
                pass
            await asyncio.sleep(3)

