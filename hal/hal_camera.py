# hal/hal_camera.py
import cv2

try:
    from picamera2 import Picamera2
    PI_CAMERA_AVAILABLE = True
except ImportError:
    PI_CAMERA_AVAILABLE = False


class CameraHAL:
    def __init__(self, bus, state, show_preview=True, resolution=(640, 480)):
        """
        Camera HAL: supports PiCamera2 (Raspberry Pi) and cv2 webcam (Laptop).
        
        :param bus: EventBus instance
        :param state: SystemState instance
        :param show_preview: Whether to show live camera feed (debug)
        :param resolution: Camera resolution (width, height)
        """
        self.bus = bus
        self.state = state
        self.show_preview = show_preview
        self.resolution = resolution

        self.cap = None
        self.pi_cam = None

        # Start camera
        self._init_camera()

    def _init_camera(self):
        """Initialize PiCamera2 if available, otherwise use cv2 webcam."""
        if PI_CAMERA_AVAILABLE:
            try:
                self.pi_cam = Picamera2()
                config = self.pi_cam.create_preview_configuration(main={"size": self.resolution})
                self.pi_cam.configure(config)
                self.pi_cam.start()
                print("[CameraHAL] Using PiCamera2")
                return
            except Exception as e:
                print(f"[CameraHAL] PiCamera2 init failed: {e}. Falling back to cv2 webcam.")

        # Fallback: cv2 webcam
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])

        if not self.cap.isOpened():
            raise RuntimeError("❌ Unable to open cv2 webcam.")
        print("[CameraHAL] Using cv2 webcam")

    def get_frame(self):
        """Get one frame from whichever camera is active."""
        if self.pi_cam:
            return self.pi_cam.capture_array()
        elif self.cap:
            ret, frame = self.cap.read()
            return frame if ret else None
        else:
            return None

    def update(self):
        """
        Called in a loop to grab frames.
        Only active if Education mode is running.
        """
        if self.state.current_mode != "education":
            return  # pause camera when not in education mode

        frame = self.get_frame()
        if frame is None:
            print("❌ Camera frame not available")
            return

        # Show preview if enabled
        if self.show_preview:
            cv2.imshow("CameraHAL Preview", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("[CameraHAL] Quit requested")
                self.release()

        # For now, just publish "frame_ready"
        # (later: YOLO, ArUco, MediaPipe analysis)
        self.bus.publish("frame_ready", {"frame": frame})

    def release(self):
        """Release camera resources."""
        if self.pi_cam:
            self.pi_cam.stop()
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        print("[CameraHAL] Camera released")
