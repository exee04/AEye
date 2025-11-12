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

        # Focus region tracking
        self.focus_region = None  # Will store (x, y, width, height) normalized coordinates

        # Event subscriptions
        self.bus.subscribe("camera_switch_res", self.on_switch_resolution)
        self.bus.subscribe("camera_capture", self.on_capture)
        self.bus.subscribe("camera_toggle_undistort", self.toggle_undistort)
        self.bus.subscribe("camera_set_focus_region", self.set_focus_region)

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
        
        # Set initial focus mode to auto
        try:
            self.pi_cam.set_controls({"AfMode": controls.AfModeEnum.Auto})
            print("[CameraHAL] ✅ Started preview with auto-focus")
        except Exception as e:
            print(f"[CameraHAL] ⚠️ Could not set auto-focus: {e}")
        
        print(f"[CameraHAL] ✅ Started preview at {self.low_res}")

    # -----------------------------
    @staticmethod
    def scale_calibration(camera_matrix, dist_coeffs, orig_res, new_res):
        """
        Scale the camera matrix to match a new resolution.
        
        Args:
            camera_matrix: Original camera matrix
            dist_coeffs: Original distortion coefficients
            orig_res: Original resolution (width, height)
            new_res: New resolution (width, height)
            
        Returns:
            tuple: (scaled_camera_matrix, dist_coeffs)
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
    def set_focus_region(self, data):
        """
        Set camera to focus on a specific region (paper borders).
        
        Args:
            data: Dictionary containing 'paper_borders' as [x1, y1, x2, y2] 
                  in normalized coordinates (0-1) relative to frame size
        """
        try:
            paper_borders = data.get("paper_borders")
            if not paper_borders or len(paper_borders) != 4:
                print("[CameraHAL] ⚠️ Invalid paper borders format. Expected [x1, y1, x2, y2]")
                return
            
            x1, y1, x2, y2 = paper_borders
            
            # Validate normalized coordinates
            if not all(0 <= coord <= 1 for coord in [x1, y1, x2, y2]):
                print("[CameraHAL] ⚠️ Paper borders must be in normalized coordinates (0-1)")
                return
            
            # Calculate center and size of the region
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            width = x2 - x1
            height = y2 - y1
            
            # Store focus region for visualization
            self.focus_region = (x1, y1, width, height)
            
            # Convert to pixel coordinates for the current resolution
            current_width, current_height = self.resolution
            pixel_center_x = int(center_x * current_width)
            pixel_center_y = int(center_y * current_height)
            pixel_width = int(width * current_width)
            pixel_height = int(height * current_height)
            
            print(f"[CameraHAL] 🔍 Setting focus region: center=({center_x:.2f}, {center_y:.2f}), size=({width:.2f}, {height:.2f})")
            print(f"[CameraHAL] 📏 Pixel coordinates: center=({pixel_center_x}, {pixel_center_y}), size=({pixel_width}, {pixel_height})")
            
            # Set focus region using libcamera controls
            try:
                # Normalized coordinates for libcamera (0.0-1.0)
                roi_x = center_x - width/2
                roi_y = center_y - height/2
                roi_width = width
                roi_height = height
                
                # Ensure ROI stays within bounds
                roi_x = max(0.0, min(roi_x, 1.0))
                roi_y = max(0.0, min(roi_y, 1.0))
                roi_width = max(0.1, min(roi_width, 1.0 - roi_x))
                roi_height = max(0.1, min(roi_height, 1.0 - roi_y))
                
                controls_dict = {
                    "AfMode": controls.AfModeEnum.Auto,
                    "AfMetering": controls.AfMeteringEnum.Windows,
                    "AfWindows": [(roi_x, roi_y, roi_width, roi_height)]
                }
                
                self.pi_cam.set_controls(controls_dict)
                print(f"[CameraHAL] ✅ Focus region set: ROI=({roi_x:.2f}, {roi_y:.2f}, {roi_width:.2f}, {roi_height:.2f})")
                
            except Exception as e:
                print(f"[CameraHAL] ⚠️ Could not set focus region via controls: {e}")
                # Fallback: try simple center focus
                try:
                    self.pi_cam.set_controls({"AfMode": controls.AfModeEnum.Auto})
                    print("[CameraHAL] 🔄 Fallback to auto-focus mode")
                except Exception as fallback_error:
                    print(f"[CameraHAL] ❌ Fallback auto-focus also failed: {fallback_error}")
                    
        except Exception as e:
            print(f"[CameraHAL] ❌ Error setting focus region: {e}")

    # -----------------------------
    def reset_focus(self):
        """Reset focus to the entire frame (auto-focus)."""
        try:
            self.pi_cam.set_controls({"AfMode": controls.AfModeEnum.Auto})
            self.focus_region = None
            print("[CameraHAL] 🔄 Focus reset to auto (full frame)")
        except Exception as e:
            print(f"[CameraHAL] ⚠️ Could not reset focus: {e}")

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
        """Apply undistortion to frame based on current resolution."""
        if not self.undistort_enabled:
            return frame

        # Scale calibration for current resolution
        if resolution == self.high_res:
            camera_matrix_scaled, dist_coeffs_scaled = self.scale_calibration(
                self.camera_matrix, self.dist_coeffs, self.orig_size, self.high_res
            )
        elif resolution == self.low_res:
            camera_matrix_scaled, dist_coeffs_scaled = self.scale_calibration(
                self.camera_matrix, self.dist_coeffs, self.orig_size, self.low_res
            )
        else:
            camera_matrix_scaled, dist_coeffs_scaled = self.camera_matrix, self.dist_coeffs

        # Apply undistortion
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

            # Draw focus region on preview if set
            if self.show_preview and self.focus_region is not None:
                frame_with_focus = frame.copy()
                h, w = frame_with_focus.shape[:2]
                x1, y1, width, height = self.focus_region
                
                # Convert normalized to pixel coordinates
                x1_px = int(x1 * w)
                y1_px = int(y1 * h)
                x2_px = int((x1 + width) * w)
                y2_px = int((y1 + height) * h)
                
                # Draw rectangle around focus region
                cv2.rectangle(frame_with_focus, (x1_px, y1_px), (x2_px, y2_px), (0, 255, 0), 2)
                cv2.putText(frame_with_focus, "Focus Region", (x1_px, y1_px - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                frame = frame_with_focus

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
                    
                    # Add focus region info
                    if self.focus_region is not None:
                        cv2.putText(
                            overlay,
                            "Focus: Paper Region",
                            (15, 80),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 255, 0),
                            2,
                            cv2.LINE_AA,
                        )
                    
                    preview_resized = cv2.resize(overlay, (640, 360))
                    cv2.imshow("Camera Preview", preview_resized)
                    cv2.waitKey(1)

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
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        sharpen_amount = 3.7  # This matches your SharpenAmt:37
        kernel = np.array([[-1, -1, -1],
                           [-1, 9, -1],
                           [-1, -1, -1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
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
