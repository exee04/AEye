import cv2
import json
import asyncio

class QRService:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.detector = cv2.QRCodeDetector()
        print("[QRService] Initialized and listening for QR codes")
        # Listen for frames from camera
        self.bus.subscribe("frame_ready", self.on_frame)
        self.start()
            
    def start(self):
        print("[QRService] Checking for connection...")
        if not self.state.hasConnection:
            print("[QRService] Initializing Initial Connection Scan")
            self.state.needWifi = True
            self.state.needQR = True
        else:
            print("[QRService] Connection is active")
            print("[QRService] Checking for account...")
            if not self.state.isLoggedIn:
                print("[QRService] Initializing Initial Login")
                self.state.needAccount = True
                self.state.needQR = True
            else:
                print("[QRService] Proceeding...")

    async def on_frame(self, data):
        if not self.state.needQR:
            return
        frame = data.get("frame")
        if frame is None:
            return

        # Try detecting QR
        text, points, _ = self.detector.detectAndDecode(frame)
        if not text:
            return

        print(f"[QRService] QR detected: {text}")

        # Publish generic scan event
        await self.bus.publish("qr_scanned", {"raw": text})

        # Try to classify type of QR
        if text.startswith("WIFI:"):
            await self.bus.publish("wifi_credentials_scanned", {"raw": text})
        else:
            try:
                parsed = json.loads(text)
                if "user" in parsed and "auth" in parsed:
                    await self.bus.publish("user_qr_scanned", parsed)
            except json.JSONDecodeError:
                pass  # just raw string QRService
