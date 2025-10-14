import cv2
import json
import asyncio

class QRService:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.detector = cv2.QRCodeDetector()
        self._processing = False
        print("[QRService] Initialized and listening for QR codes")

        # Subscriptions
        self.bus.subscribe("frame_ready", self.on_frame)
        self.bus.subscribe("cancel_login", self.on_cancel)
        self.bus.subscribe("button_pressed", self.on_button)

        self.start()

    def start(self):
        print("[QRService] Checking for connection...")
        if not self.state.hasConnection:
            print("[QRService] No Wi-Fi, scanning for Wi-Fi QR...")
            self.state.needWifi = True
            self.state.needQR = True
        elif not self.state.isLoggedIn:
            print("[QRService] Wi-Fi OK, scanning for Account QR...")
            self.state.needAccount = True
            self.state.needQR = True
        else:
            print("[QRService] System ready and logged in.")

    async def on_frame(self, data):
        if not getattr(self.state, "needQR", False):
            return
        frame = data.get("frame")
        if frame is None or self._processing:
            return

        self._processing = True
        try:
            text, _, _ = self.detector.detectAndDecode(frame)
            if not text:
                return

            print(f"[QRService] QR detected: {text}")
            await self.bus.publish("qr_scanned", {"raw": text})

            # --- Step 1: Wi-Fi QR stage ---
            if self.state.needWifi and text.startswith("WIFI:"):
                await self.bus.publish("wifi_credentials_scanned", {"raw": text})
                print("[QRService] Wi-Fi credentials detected, connecting...")
                # simulate success (you'll replace this with actual Wi-Fi connection logic)
                self.state.hasConnection = True
                self.state.needWifi = False
                print("[QRService] Wi-Fi connected. Moving to Account QR stage.")
                self.state.needAccount = True
                return

            # --- Step 2: Account QR stage ---
            if self.state.needAccount:
                try:
                    parsed = json.loads(text)
                    user_id = parsed.get("id") or parsed.get("uuid")
                    username = parsed.get("username")
                    if user_id and username:
                        print(f"[QRService] Account QR OK → user={username}, id={user_id}")
                        self.state.user_id = user_id
                        self.state.username = username
                        self.state.isLoggedIn = True
                        self.state.needAccount = False
                        self.state.needQR = False
                        await self.bus.publish("login_success", {
                            "id": user_id,
                            "username": username
                        })
                    else:
                        print("[QRService] Invalid account QR format.")
                except json.JSONDecodeError:
                    print("[QRService] Account QR not valid JSON.")
        finally:
            await asyncio.sleep(0.05)
            self._processing = False

    async def on_cancel(self, data):
        """
        Cancels the current process (Wi-Fi or Account) and goes offline.
        """
        print("[QRService] Cancel event received — switching to offline mode.")
        self.state.needWifi = False
        self.state.needAccount = False
        self.state.needQR = False
        self.state.offline_mode = True
        await self.bus.publish("offline_mode_enabled", {"reason": "user_cancelled"})

    async def on_button(self, data):
        """
        Optional — if button events are generic, check payload.
        """
        btn = data.get("button")
        if btn in ("cancel", "cancel_login", "offline"):
            await self.on_cancel(data)

