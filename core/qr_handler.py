import cv2


class QRHandler:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.detector = cv2.QRCodeDetector()
        self._last_handled = None
        self._frame_counter = 0  # Initialize frame counter
        self.bus.subscribe("frame_ready", self.onFrame)

    async def onFrame(self, data):
        if not self.state.needQR:
            return
        frame = data.get("frame")
        if frame is None:
            return

        # Increment counter and skip processing if not 4th frame
        self._frame_counter = (self._frame_counter + 1) % 4
        if self._frame_counter != 0:
            return

        text, points, _ = self.detector.detectAndDecode(frame)
        if points is not None and len(points) > 0:
            hull = cv2.convexHull(points)
        else:
            hull = []
        if not text:
            return

        if text == self._last_handled:
            return

        if not self.state.hasConnection:
            if text.startswith("WIFI:"):
                await self.bus.publish("wifi_connect", {"raw": text})
            return

        if self.state.hasConnection and not self.state.hasAccount:
            await self.bus.publish("account_connect", {"raw": text})
            return

        if self.state.hasConnection and self.state.hasAccount:
            self.state.needQR = False
            return
