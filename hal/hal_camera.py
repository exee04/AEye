import cv2
import asyncio
import time

try:
    from picamera2 import Picamera2
    from libcamera import Transform, ColorSpace
    PI_CAMERA_AVAILABLE = True
except ImportError:
    PI_CAMERA_AVAILABLE = False


class CameraHAL:
    def __init__(
        self,
        bus,
        state,
        show_preview=False,          # unified preview flag
        resolution=(2304, 1296),
        target_fps=15,
    ):
        self.bus = bus
        self.state = state
        self.show_preview = show_preview
        self.resolution = resolution
        self.target_fps = target_fps
        self.min_interval = 1.0 / target_fps
        self.last_frame_time = 0

        # Camera handles
        self.cap = None
        self.pi_cam = None
        self.using_pi = False
        self.qr_data = None

        bus.subscribe("qr_detected", self.on_qr_detected)
        self._init_camera()

    # ------------------------------------------------------------------
    def _init_camera(self):
        """Initialize PiCamera2 (IMX708) or fallback to cv2 webcam."""
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
                    buffer_count=2,  # reduce load
                )

                self.pi_cam.configure(config)
                self.pi_cam.start()
                self.using_pi = True

                # Normal exposure / brightness — natural image
                self.pi_cam.set_controls({
                    "FrameDurationLimits": (
                        int(1e6 / self.target_fps),
                        int(1e6 / self.target_fps),
                    ),
                    "ExposureTime": 16000,  # normal exposure
                    "AnalogueGain": 2.0,    # normal brightness
                })

                print(f"[CameraHAL] ✅ Using PiCamera2 (IMX708) {self.resolution} @ {self.target_fps} FPS")
                return

            except Exception as e:
                print(f"[CameraHAL] ⚠️ PiCamera2 init failed: {e}. Falling back to cv2 webcam.")

        # fallback webcam
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)

        if not self.cap.isOpened():
            raise RuntimeError("❌ Unable to open camera device.")
        print(f"[CameraHAL] ✅ Using OpenCV webcam {self.resolution} @ {self.target_fps} FPS")

    # ------------------------------------------------------------------
    def get_frame(self):
        """Capture a frame."""
        if self.using_pi:
            frame = self.pi_cam.capture_array("main")
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        elif self.cap:
            ret, frame = self.cap.read()
            return frame if ret else None
        return None

    def update(self):
        """Capture + optional preview + publish event."""
        now = time.time()
        if now - self.last_frame_time < self.min_interval:
            return None, None
        self.last_frame_time = now

        frame = self.get_frame()
        if frame is None:
            print("❌ Camera frame not available")
            return None, None

        # Preview downscaled for SSH/Wayland (no need for full res)
        if self.show_preview:
            preview = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
            cv2.imshow("CameraHAL Preview", preview)
            if cv2.waitKey(1) & 0xFF == ord('p'):
                print("[CameraHAL] Quit requested")
                self.release()
        else:
            preview = None

        asyncio.get_event_loop().create_task(
            self.bus.publish("frame_ready", {"frame": frame})
        )

        # Small rest period to ease CPU/GPU load
        time.sleep(0.005)
        return frame, preview

    # ------------------------------------------------------------------
    def release(self):
        """Release resources."""
        if self.pi_cam:
            self.pi_cam.stop()
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        print("[CameraHAL] 📴 Camera released")

    # ------------------------------------------------------------------
    async def on_qr_detected(self, data):
        self.qr_data = data.get("raw")
