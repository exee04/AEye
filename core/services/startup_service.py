import asyncio

class StartupService:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.online_selected = False
        self.offline_selected = False

        # Subscribe to button press and QR events
        bus.subscribe("button_main_pressed", self.on_main_button)
        bus.subscribe("wifi_connected", self.on_wifi_connected)
        bus.subscribe("login_success", self.on_login_success)
        bus.subscribe("login_failed", self.on_login_failed)

    async def start(self):
        """Initialize system startup sequence."""
        print("[StartupService] Starting system initialization...")
        self.state.buttons_enabled = ["main"]
        await self.bus.publish("tts_speak", {"text": "Press the main button to start in online mode, or wait for offline mode."})

        # Wait for user decision for ~10 seconds
        for _ in range(10):
            if self.online_selected or self.offline_selected:
                break
            await asyncio.sleep(1)

        if not self.online_selected:
            print("[StartupService] No response. Entering offline mode.")
            await self.enter_offline_mode()
        else:
            print("[StartupService] Online mode selected.")
            await self.start_online_mode()

    async def on_main_button(self, _):
        """Triggered when user presses main button."""
        if not self.online_selected and not self.offline_selected:
            self.online_selected = True

    async def start_online_mode(self):
        """Proceed with Wi-Fi and account login sequence."""
        self.state.needWifi = True
        await self.bus.publish("tts_speak", {"text": "Please scan your Wi-Fi QR code."})
        self.state.needQR = True  # QRService now starts detecting Wi-Fi QR

    async def on_wifi_connected(self, data):
        """Once Wi-Fi connects successfully."""
        print(f"[StartupService] Wi-Fi connected: {data.get('ssid')}")
        self.state.needQR = True
        await self.bus.publish("tts_speak", {"text": "Wi-Fi connected. Please scan your account QR."})
        await self.bus.publish("await_account_qr", {})

    async def on_login_success(self, data):
        """Once account login verified."""
        print(f"[StartupService] Login success for {data.get('username')}")
        await self.bus.publish("tts_speak", {"text": f"Welcome {data.get('username')}!"})
        await self.enable_full_system()

    async def on_login_failed(self, _):
        print("[StartupService] Login failed. Entering offline mode.")
        await self.enter_offline_mode()

    async def enter_offline_mode(self):
        """Skip all cloud-dependent modules."""
        self.state.hasConnection = False
        self.state.isLoggedIn = False
        self.state.mode = "offline"
        await self.bus.publish("tts_speak", {"text": "Offline mode activated."})
        await self.enable_full_system()

    async def enable_full_system(self):
        """Enable all buttons and start other modules."""
        self.state.buttons_enabled = ["main", "learn", "quiz", "volume", "wifi"]
        await self.bus.publish("system_ready", {"mode": self.state.mode})
        print("[StartupService] System fully initialized.")

