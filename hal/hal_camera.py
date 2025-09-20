# hal/hal_camera.py
import cv2
import asyncio

try:
    from picamera2 import Picamera2
    PI_CAMERA_AVAILABLE = True
except ImportError:
    PI_CAMERA_AVAILABLE = False


class CameraHAL:
    def __init__(self, bus, state, show_preview=True, resolution=(640, 480)):
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
        """Initialize PiCamera2 if available, otherwise use cv2 webcam."""
        if PI_CAMERA_AVAILABLE:
            try:
                self.pi_cam = Picamera2()
                config = self.pi_cam.create_preview_configuration(
                    main={"size": self.resolution}
                )
                self.pi_cam.configure(config)
                self.pi_cam.start()
                self.using_pi = True
                print("[CameraHAL] Using PiCamera2 with cv2 preview")
                return
            except Exception as e:
                print(f"[CameraHAL] PiCamera2 init failed: {e}. Falling back to cv2 webcam.")

        # fallback webcam
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])

        if not self.cap.isOpened():
            raise RuntimeError("❌ Unable to open cv2 webcam.")
        print("[CameraHAL] Using cv2 webcam")

    def get_frame(self):
        """Grab a frame from PiCamera2 or cv2 webcam."""
        if self.using_pi:
            frame = self.pi_cam.capture_array()
            # PiCamera2 gives RGB → convert to BGR for OpenCV
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return frame
        elif self.cap:
            ret, frame = self.cap.read()
            return frame if ret else None
        return None

    def update(self):
        """Continuously fetch frames and show preview if enabled."""
        frame = self.get_frame()
        if frame is None:
            print("❌ Camera frame not available")
            return

        # =============================
        # Debug overlays
        # =============================
    
        

        mode_text = f"Mode: {self.state.current_mode}"
        layer_text = "Layer: Primary" if self.state.primary else "Layer: Secondary"
        volume = "Volume: " + str(self.state.volume)

        if self.qr_data:
            cv2.putText(frame, f"QR: {self.qr_data[:30]}...", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

        cv2.putText(frame, volume, (435, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1,
                    (0,225,0), 2, cv2.LINE_AA)
        
        cv2.putText(frame, mode_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1,
                    (0, 255, 0), 2, cv2.LINE_AA)

        cv2.putText(frame, layer_text, (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 1,
                    (255, 255, 0), 2, cv2.LINE_AA)

        if self.state.current_mode == "education":
            submode_text = f"Submode: {self.state.education_submode}"
            cv2.putText(frame, submode_text, (10, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 1,
                        (0, 200, 255), 2, cv2.LINE_AA)

        net_text = f"Network: {self.state.network_status}"
        cv2.putText(frame, net_text, (10, 150),
            cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)

        # =============================
        # Show preview
        # =============================
        if self.show_preview:
            cv2.imshow("CameraHAL Preview", frame)
            if cv2.waitKey(1) & 0xFF == ord('p'):
                print("[CameraHAL] Quit requested")
                self.release()

        # Publish "frame_ready" event
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
