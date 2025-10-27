import cv2
import asyncio
import time

try:
    from picamera2 import Picamera2
    from libcamera import Transform, ColorSpace
    PI_CAMERA_AVAILABLE = True
except ImportError:
    PI_CAMERA_AVAILABLE = False

# [0] Resolution: (1536, 864), FPS: 120.13, Bit depth: 10
# [1] Resolution: (2304, 1296), FPS: 56.03, Bit depth: 10
# [2] Resolution: (4608, 2592), FPS: 14.35, Bit depth: 10


class CameraHAL:
    def __init__(
        self,
        bus,
        state,
        show_preview=False,
        resolution=(2304, 1296),
        target_fps=15,
        edu_mode=None
    ):
        self.bus = bus
        self.state = state
        self.edu_mode = edu_mode
        self.show_preview = show_preview
        self.resolution = resolution
        self.state.cam_width, self.state.cam_height = resolution
        self.target_fps = target_fps
        self.min_interval = 1.0 / target_fps
        self.last_frame_time = 0
        
        # Camera handles
        self.cap = None
        self.pi_cam = None
        self.using_pi = False
        self.qr_data = None
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
                    buffer_count=2,
                )
                config["controls"]["AfMode"] = 2
                self.pi_cam.configure(config)
                self.pi_cam.start()
                self.using_pi = True

                # Normal exposure / brightness — natural image
                self.pi_cam.set_controls({
                    "FrameDurationLimits": (
                        int(1e6 / self.target_fps),
                        int(1e6 / self.target_fps),
                    ),
                    "ExposureTime": 40000,
                    "AnalogueGain": 8.0,
                    "AfMode": 2,
                })

                print(f"[CameraHAL] ✅ Using PiCamera2 (IMX708) {self.resolution} @ {self.target_fps} FPS")
                return
            except Exception as e:
                print(f"[CameraHAL] ⚠️ PiCamera2 init failed: {e}. Falling back to cv2 webcam.")

        # Fallback webcam
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

    # ------------------------------------------------------------------
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

        # Publish frame asynchronously
        asyncio.get_event_loop().create_task(
            self.bus.publish("frame_ready", {"frame": frame})
        )

        preview = None
        if self.show_preview:
            # Check current mode
            current_mode = getattr(self.state, "current_system_mode", "Unknown")

            # Use processed frame if we're in EducationMode and it exists
            if (
                current_mode == "EducationMode"
                and self.edu_mode
                and getattr(self.edu_mode, "frame", None) is not None
            ):
                preview = self.edu_mode.frame
                label = "EducationMode"
            else:
                # Always fallback to the live camera feed for all other modes
                preview = frame
                label = current_mode

            # Draw overlay
            if preview is not None:
                overlay = preview.copy()
                cv2.putText(
                    overlay,
                    f"Mode: {label}",
                    (15, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )
                preview_resized = cv2.resize(overlay, (640, 360))
                cv2.imshow("Camera Preview", preview_resized)
                cv2.waitKey(1)

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
