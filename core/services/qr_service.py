import cv2
import json
import asyncio

class QRService:
    def __init__(self, bus):
        self.bus = bus
        self.detector = cv2.QRCodeDetector()
        print("[QRService] Initialized and listening for QR codes")

        # Listen for frames from camera
        self.bus.subscribe("frame_ready", self.on_frame)

    async def on_frame(self, data):
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
                pass  # just raw string QR
