# hal/hal_camera.py
import cv2
import asyncio

try:
    from picamera2 import Picamera2
    from libcamera import Transform, ColorSpace
    PI_CAMERA_AVAILABLE = True
except ImportError:
    PI_CAMERA_AVAILABLE = False


class CameraHAL:
    def __init__(self, bus, state, show_preview=True, resolution=(2304, 1296)):
        self.bus = bus
        self.state = state
        self.show_preview = show_preview
        self.resolution = resolution

        self.cap = None
        self.pi_cam = None
        self.using_pi = False
        self.qr_data = None
        bus.subscribe("qr_detected", self.on_qr_detected)

        self._init_camera()

    def _init_camera(self):
        """Initialize PiCamera2 (optimized for IMX708) or fallback to OpenCV webcam."""
        if PI_CAMERA_AVAILABLE:
            try:
                self.pi_cam = Picamera2()
                config = self.pi_cam.create_preview_configuration(
                    main={
                        "size": self.resolution,
                        "format": "XBGR8888",
                    },
                    transform=Transform(hflip=0, vflip=0),
                    colour_space=ColorSpace.Sycc(),
                    buffer_count=4,
                )
                self.pi_cam.configure(config)
                self.pi_cam.start()
                self.using_pi = True
                print(f"[CameraHAL] ✅ Using PiCamera2 (IMX708) at {self.resolution}")
                return
            except Exception as e:
                print(f"[CameraHAL] ⚠️ PiCamera2 init failed: {e}. Falling back to cv2 webcam.")

        # fallback to USB / cv2 camera
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])

        if not self.cap.isOpened():
            raise RuntimeError("❌ Unable to open camera device.")
        print("[CameraHAL] Using cv2 webcam")

    def get_frame(self):
        """Grab a frame from PiCamera2 or cv2 webcam."""
        if self.using_pi:
            frame = self.pi_cam.capture_array("main")
            # PiCamera2 gives RGB; convert to BGR for OpenCV compatibility
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return frame
        elif self.cap:
            ret, frame = self.cap.read()
            return frame if ret else None
        return None

    def update(self):
        """Fetch frame, show preview, and publish event."""
        frame = self.get_frame()
        if frame is None:
            print("❌ Camera frame not available")
            return

        # Optional: downscale for faster processing
        # frame = cv2.resize(frame, (960, 540))

        if self.show_preview:
            cv2.imshow("CameraHAL Preview", frame)
            if cv2.waitKey(1) & 0xFF == ord('p'):
                print("[CameraHAL] Quit requested")
                self.release()

        # Publish frame
        asyncio.get_event_loop().create_task(
            self.bus.publish("frame_ready", {"frame": frame})
        )

    def release(self):
        """Release camera resources."""
        if self.pi_cam:
            self.pi_cam.stop()
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        print("[CameraHAL] Camera released")

    async def on_qr_detected(self, data):
        self.qr_data = data.get("raw")

