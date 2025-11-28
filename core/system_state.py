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
        self.accountInfo = None
        self.current_user_uuid = None
        self.current_username = None
        self.current_system_mode = "Initialization"
        self.current_network_state = "Unknown"
        self.current_audio_mode = "VolumeMode"
        self.hasBraillePaper = False
        self.camera_calibration = None
        
        # ------------ RESTORE THESE TWO ------------
        self.language = "en"          # ← REQUIRED
        self.volume = 100             # already existed
        self.voiceSpeed = 100         # already existed
        # --------------------------------------------------

        # Subscriptions
        bus.subscribe("button_press", self.SkipStartup)
        bus.subscribe("network_status", self.OnNetworkChange)


    # ================================================================
    #  ACCOUNT LOADING
    # ================================================================
    async def OnAccountLoaded(self, data):
        """
        Called when AccountHandler emits:
        bus.publish("account_loaded", {"uuid":..., "username":...})
        """

        self.hasAccount = True
        self.current_user_uuid = data.get("uuid")
        self.current_username = data.get("username")

        print(f"[SystemState] User logged in: {self.current_username} ({self.current_user_uuid})")


    # ================================================================
    #  MODE SWITCHING SYSTEM-WIDE
    # ================================================================
    async def setEducationSubMode(self, new_mode):
        """
        Called by NavigationHandler.
        Emits global mode_change event consumed by EducationMode.
        """
        if new_mode == self.education_submode:
            print(f"[SystemState] EducationMode already in '{new_mode}'")
            return

        print(f"[SystemState] EducationMode submode changed: {self.education_submode} → {new_mode}")
        self.education_submode = new_mode

        # Publish mode change for EducationMode
        await self.bus.publish("mode_change", {"new_mode": new_mode})


    # ================================================================
    #  SKIP STARTUP VIA BUTTON
    # ================================================================
    async def SkipStartup(self, data):
        if self.current_system_mode != "Initialization":
            return
        pin = data.get("pin")
        if pin == 25:
            self.skipped_startup = True
            self.needQR = False


    # ================================================================
    #  NETWORK STATE UPDATES
    # ================================================================
    async def OnNetworkChange(self, data):
        self.hasConnection = data.get("connected", False)
        self.network_status = data.get("status", "Unknown")


    # ================================================================
    #  STARTUP FLOW
    # ================================================================
    async def _scan_phase(self, prompt, check_condition, reminder_text):
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


    # ================================================================
    #  GENERAL STARTUP LOGIC
    # ================================================================
    async def OnStartup(self):
        self.needQR = True
        self.current_system_mode = "Initialization"

        # Phase 1: Wi-Fi
        wifi_result = await self._scan_phase(
            prompt="Scan Wi-Fi QR",
            check_condition=lambda: self.hasConnection,
            reminder_text="Still scanning for Wi-Fi.",
        )

        if wifi_result != "SUCCESS":
            return await self._start_fallback_mode(wifi_result, wifi_connected=False)

        # Phase 2: Account
        account_result = await self._scan_phase(
            prompt="Scan Account QR",
            check_condition=lambda: self.hasAccount,
            reminder_text="Still waiting for account QR.",
        )

        if account_result != "SUCCESS":
            return await self._start_fallback_mode(account_result, wifi_connected=True)

        # FULL ONLINE MODE
        await self.bus.publish("init_api")
        self.current_network_state = "ONLINE_FULL"
        self.current_system_mode = "Idle"
        self.needQR = False
        await self.bus.publish("tts", {"text": "Setup complete."})


    # ================================================================
    #  AUDIO CONTROLS
    # ================================================================
    async def AudioFunctionUp(self):
        if self.current_audio_mode == "VolumeMode":
            if self.volume + 20 > self.MAX_VOLUME:
                print("Already at max volume")
            else:
                self.volume += 20
                print(f"Volume → {self.volume}")
        else:
            if self.voiceSpeed + 20 > self.MAX_VOICE_SPEED:
                print("Already at max voice speed")
            else:
                self.voiceSpeed += 20
                print(f"Voice speed → {self.voiceSpeed}")

    async def AudioFunctionDown(self):
        if self.current_audio_mode == "VolumeMode":
            if self.volume - 20 < self.MIN_VOLUME:
                print("Already at min volume")
            else:
                self.volume -= 20
                print(f"Volume → {self.volume}")
        else:
            if self.voiceSpeed - 20 < self.MIN_VOICE_SPEED:
                print("Already at min voice speed")
            else:
                self.voiceSpeed -= 20
                print(f"Voice speed → {self.voiceSpeed}")

    async def AudioFunctionToggle(self):
        self.current_audio_mode = (
            "VolumeMode" if self.current_audio_mode != "VolumeMode" else "VoiceMode"
        )
        print(f"Audio mode → {self.current_audio_mode}")

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

