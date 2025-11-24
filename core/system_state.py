import asyncio


class SystemState:
    STARTUP_TIMEOUT = 40
    REMINDER_INTERVAL = 15
    MIN_VOLUME = 0 
    MAX_VOLUME = 200
    MIN_VOICE_SPEED = 100 
    MAX_VOICE_SPEED = 280
    def __init__(self, bus):
        self.bus = bus

        # State variables
        self.cam_width = None
        self.cam_height = None

        self.skipped_startup = False
        self.needQR = False
        self.hasConnection = False
        self.network_status = "Unknown"
        self.hasAccount = False
        self.account_name = "Unknown"

        self.current_system_mode = "Initialization"
        self.current_network_state = "Unknown"
        self.current_audio_mode = "VolumeMode"
        self.hasBraillePaper = False

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
        if pin == 25:
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

    async def _start_fallback_mode(self, reason, wifi_connected=False):
        """
        Handle transition into offline or partial-online mode.
        - If Wi-Fi was connected but account was skipped/timed out → PARTIAL_ONLINE
        - If no Wi-Fi connection → OFFLINE_MODE
        """
        if wifi_connected:
            msg = (
                "Account setup skipped. Starting in partial online mode."
                if reason == "SKIPPED"
                else "No account QR found. Starting in partial online mode."
            )
            self.current_network_state = "PARTIAL_ONLINE"
            await self.bus.publish("init_api")
        else:
            msg = (
                "Starting in offline mode."
                if reason == "SKIPPED"
                else "No QR found. Starting in offline mode."
            )
            self.current_network_state = "OFFLINE_MODE"

        await self.bus.publish("tts", {"text": msg})
        self.needQR = False
        self.current_system_mode = "Idle"

    async def OnStartup(self):
        """Handles startup logic with timeout, reminders, and fallback modes."""
        self.needQR = True
        self.current_system_mode = "Initialization"

        # --- Phase 1: Wi-Fi ---
        wifi_result = await self._scan_phase(
            prompt="Scan Wi-Fi QR",
            check_condition=lambda: self.hasConnection,
            reminder_text="Still scanning for Wi-Fi.",
        )

        if wifi_result != "SUCCESS":
            # No Wi-Fi → Fully offline
            return await self._start_fallback_mode(wifi_result, wifi_connected=False)

        # --- Phase 2: Account ---
        account_result = await self._scan_phase(
            prompt="Scan Account QR",
            check_condition=lambda: self.hasAccount,
            reminder_text="Still waiting for account QR.",
        )

        if account_result != "SUCCESS":
            # Wi-Fi connected but no account → Partial online
            return await self._start_fallback_mode(account_result, wifi_connected=True)

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


    async def AudioFunctionUp(self):
        if self.current_audio_mode == "VolumeMode":
            if (self.volume + 20) > self.MAX_VOLUME:
                print("Already at max volume")
            else:
                self.volume = self.volume + 20 
                print("Increased volume to " + str(self.volume))
        if self.current_audio_mode == "VoiceMode":
            if (self.voiceSpeed + 20) > self.MAX_VOICE_SPEED:
                print("Already at max voice speed")
            else:
                self.voiceSpeed = self.voiceSpeed + 20
                print("Increased voice speed to " + str(self.voiceSpeed))

    async def AudioFunctionDown(self):
        if self.current_audio_mode == "VolumeMode":
            if (self.volume - 20) < self.MIN_VOLUME:
                print("Already at min volume")
            else:
                self.volume = self.volume - 20 
                print("Decreased volume to " + str(self.volume))
        if self.current_audio_mode == "VoiceMode":
            if (self.voiceSpeed - 20) < self.MIN_VOICE_SPEED:
                print("Already at min voice speed")
            else:
                self.voiceSpeed = self.voiceSpeed - 20
                print("Decreased voice speed to " + str(self.voiceSpeed))


    async def AudioFunctionToggle(self):
        self.current_audio_mode = "VolumeMode" if self.current_audio_mode != "VolumeMode" else "VoiceMode"
        print(str(self.current_audio_mode))


