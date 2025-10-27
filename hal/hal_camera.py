import cv2
import asyncio
import time
import numpy as np
from picamera2 import Picamera2
from libcamera import controls

class CameraHAL:
    def __init__(self, bus, state, show_preview=False, edu_mode=None):
        self.bus = bus
        self.state = state
        self.show_preview = show_preview
        self.edu_mode = edu_mode

        # Calibration originally done at 2304x1296
        self.camera_matrix = np.array([
            [9.98753294e+02, 0.0, 1.15982896e+03],
            [0.0, 1.00373051e+03, 6.50888400e+02],
            [0.0, 0.0, 1.0]
        ])
        self.dist_coeffs = np.array([[-0.089, 0.142, -0.001, -0.002, -0.132]])
        self.orig_size = (2304, 1296)

        # Working resolutions
        self.low_res = (1536, 864)
        self.high_res = (4608, 2592)
        self.resolution = self.low_res
        self.undistort_enabled = True

        # Camera setup
        self.pi_cam = Picamera2()
        self.preview_config = None
        self.capture_config = None

        # Event subscriptions
        self.bus.subscribe("camera_switch_res", self.on_switch_resolution)
        self.bus.subscribe("camera_capture", self.on_capture)
        self.bus.subscribe("camera_toggle_undistort", self.toggle_undistort)

        self._init_camera()

    # -----------------------------
    def _init_camera(self):
        """Initialize PiCamera2 with preview and capture configurations."""
        self.preview_config = self.pi_cam.create_preview_configuration(
            main={"size": self.low_res, "format": "RGB888"}
        )
        self.capture_config = self.pi_cam.create_still_configuration(
            main={"size": self.high_res, "format": "RGB888"}
        )
        self.pi_cam.configure(self.preview_config)
        self.pi_cam.start()
        print(f"[CameraHAL] ✅ Started preview at {self.low_res}")

    # -----------------------------
    def scale_calibration(camera_matrix, dist_coeffs, orig_res, new_res):
        """
        Scale the camera matrix to match a new resolution.
        """
        scale_x = new_res[0] / orig_res[0]
        scale_y = new_res[1] / orig_res[1]

        new_camera_matrix = camera_matrix.copy()
        new_camera_matrix[0, 0] *= scale_x  # fx
        new_camera_matrix[1, 1] *= scale_y  # fy
        new_camera_matrix[0, 2] *= scale_x  # cx
        new_camera_matrix[1, 2] *= scale_y  # cy

        return new_camera_matrix, dist_coeffs
   # -----------------------------
    def get_frame(self):
        """Capture frame from PiCamera2."""
        try:
            frame = self.pi_cam.capture_array("main")
            return frame
        except Exception as e:
            print("[CameraHAL] Error capturing frame:", e)
            return None

    # -----------------------------
    def undistort_frame(self, frame, resolution):
        if not self.undistort_enabled:
            return frame

        # --- Original calibration resolution ---
        orig_res = (2304, 1296)

        # --- Helper function for scaling calibration ---
        def scale_calibration(camera_matrix, dist_coeffs, orig_res, new_res):
            scale_x = new_res[0] / orig_res[0]
            scale_y = new_res[1] / orig_res[1]

            new_camera_matrix = camera_matrix.copy()
            new_camera_matrix[0, 0] *= scale_x  # fx
            new_camera_matrix[1, 1] *= scale_y  # fy
            new_camera_matrix[0, 2] *= scale_x  # cx
            new_camera_matrix[1, 2] *= scale_y  # cy

            return new_camera_matrix, dist_coeffs

        # --- Scale according to active resolution ---
        if resolution == (4608, 2592):
            camera_matrix_scaled, dist_coeffs_scaled = scale_calibration(
                self.camera_matrix, self.dist_coeffs, orig_res, (4608, 2592)
            )
        elif resolution == (1536, 864):
            camera_matrix_scaled, dist_coeffs_scaled = scale_calibration(
                self.camera_matrix, self.dist_coeffs, orig_res, (1536, 864)
            )
        else:
            camera_matrix_scaled, dist_coeffs_scaled = self.camera_matrix, self.dist_coeffs

        # --- Apply undistortion ---
        frame_undistorted = cv2.undistort(frame, camera_matrix_scaled, dist_coeffs_scaled)

        return frame_undistorted

    # -----------------------------
    async def update(self):
        """Main frame capture + preview display + publish to bus."""
        while True:
            frame = self.get_frame()
            if frame is None:
                await asyncio.sleep(0.02)
                continue

            # Publish current frame (async)
            asyncio.create_task(
                self.bus.publish("frame_ready", {"frame": frame})
            )

            # --- PREVIEW (your original logic) ---
            preview = None
            if self.show_preview:
                current_mode = getattr(self.state, "current_system_mode", "Unknown")

                if (
                    current_mode == "EducationMode"
                    and self.edu_mode
                    and getattr(self.edu_mode, "frame", None) is not None
                ):
                    preview = self.edu_mode.frame
                    label = "EducationMode"
                else:
                    preview = frame
                    label = current_mode

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
            await asyncio.sleep(0.01)

    # -----------------------------
    async def on_switch_resolution(self, data):
        """Handle resolution switching."""
        res = tuple(data.get("res", self.low_res))
        try:
            self.pi_cam.stop()
            if res == self.low_res:
                self.pi_cam.configure(self.preview_config)
                print("[CameraHAL] 🔁 Switched to preview mode.")
            elif res == self.high_res:
                self.pi_cam.configure(self.capture_config)
                print("[CameraHAL] 🔁 Switched to capture mode.")
            else:
                print(f"[CameraHAL] ⚠️ Unsupported resolution: {res}")
                return
            self.pi_cam.start()
            self.resolution = res
        except Exception as e:
            print(f"[CameraHAL] ⚠️ Resolution switch failed: {e}")

    def apply_braille_filters(self, frame):
        """Apply Braille-optimized filters matching the filter configuration."""
        # --- Convert to grayscale (always done for processing) ---
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # --- CLAHE (ON in your config) ---
        # Using same parameters as your first code
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # --- Sharpen (ON in your config with amount 37) ---
        # Convert trackbar value 37 to actual sharpen amount (37/10 = 3.7)
        sharpen_amount = 3.7  # This matches your SharpenAmt:37
        kernel = np.array([[-1, -1, -1],
                           [-1, 9, -1],
                           [-1, -1, -1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        
        # Alternative sharpen method (more similar to your first code):
        # blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
        # sharpened = cv2.addWeighted(enhanced, 1.0 + sharpen_amount, blurred, -sharpen_amount, 0)
        
        # --- Convert back to BGR for consistency across modules ---
        return sharpened


    # -----------------------------
    async def on_capture(self, data):
        """Capture and save both raw and filtered high-res images."""
        try:
            print("[CameraHAL] 📸 Capturing high-res image...")
            self.pi_cam.stop()
            self.pi_cam.configure(self.capture_config)
            self.pi_cam.start()
            await asyncio.sleep(0.4)  # settle exposure/focus

            frame = self.get_frame()
            if frame is None:
                print("[CameraHAL] ❌ Capture failed.")
                return

            # --- Undistort raw image ---
            raw_undistorted = self.undistort_frame(frame, self.high_res)

            # --- Apply filters for Braille ---
            filtered = self.apply_braille_filters(raw_undistorted)

            # --- Save both versions ---
            import os

            timestamp = int(time.time())
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            save_dir = os.path.join(project_root, "core", "cache", "captures")
            os.makedirs(save_dir, exist_ok=True)

            raw_path = os.path.join(save_dir, f"capture_raw_{timestamp}.png")
            filtered_path = os.path.join(save_dir, f"capture_filtered_{timestamp}.png")


            cv2.imwrite(raw_path, raw_undistorted)
            cv2.imwrite(filtered_path, filtered)

            print(f"[CameraHAL] 💾 Saved:\n ├─ Raw → {raw_path}\n └─ Filtered → {filtered_path}")

            # Publish both frames
            await self.bus.publish("camera_image_captured", {
                "raw": raw_undistorted,
                "filtered": filtered,
                "resolution": self.high_res
            })

            # Return to preview mode
            self.pi_cam.stop()
            self.pi_cam.configure(self.preview_config)
            self.pi_cam.start()
            print("[CameraHAL] ✅ Capture done, back to preview mode.")

        except Exception as e:
            print(f"[CameraHAL] ⚠️ Error during capture: {e}")

    # -----------------------------
    async def toggle_undistort(self, data):
        """Toggle undistortion via pub/sub event."""
        flag = data.get("enabled", True)
        self.undistort_enabled = flag
        print(f"[CameraHAL] 🔧 Undistortion {'enabled' if flag else 'disabled'}.")

    # -----------------------------
    def release(self):
        self.pi_cam.stop()
        cv2.destroyAllWindows()
        print("[CameraHAL] 📴 Camera released.")

