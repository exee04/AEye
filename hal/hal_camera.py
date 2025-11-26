# core/camera_hal.py
import os
import time
import asyncio
import numpy as np
import cv2
from picamera2 import Picamera2

class CameraHAL:
    """
    High-resolution logic + low-heat preview CameraHAL:
      - Preview stream: FULL calibration resolution (2304x1296), RGB888, capped at 10 FPS.
      - Capture stream: 4608x2592 RGB888 still images (on-demand).
      - No intrinsics scaling; full resolution matches calibration.
      - Publishes: bus.publish("frame_ready", {"frame": frame})
    """

    # Original calibration resolution (intrinsics were computed at this resolution)
    ORIG_RES = (2304, 1296)

    # Preview resolution (match calibration 1:1)
    PREVIEW_RES = (2304, 1296)

    # Capture resolution (high-quality stills)
    CAPTURE_RES = (4608, 2592)

    # Default preview FPS cap
    DEFAULT_FPS = 10

    def __init__(self, bus, state, show_preview=False, fps=DEFAULT_FPS):
        self.bus = bus
        self.state = state
        self.show_preview = show_preview
        self.fps = max(1, int(fps))
        self.frame_interval = 1.0 / float(self.fps)

        # === REAL CALIBRATION @ 2304x1296 ===
        self.camera_matrix = np.array([
            [9.98753294e+02, 0.0, 1.15982896e+03],
            [0.0, 1.00373051e+03, 6.50888400e+02],
            [0.0, 0.0, 1.0]
        ], dtype=np.float64)

        self.dist_coeffs = np.array([[-0.089, 0.142, -0.001, -0.002, -0.132]],
                                    dtype=np.float64)

        # Store sizes
        self.preview_res = tuple(self.PREVIEW_RES)
        self.capture_res = tuple(self.CAPTURE_RES)

        # Write intrinsics to system state (NO scaling)
        try:
            self.state.camera_calibration = {
                "intrinsics": {
                    "K": self.camera_matrix.tolist(),
                    "D": self.dist_coeffs.tolist(),
                    "resolution": self.preview_res
                },
                "extrinsics": None
            }
        except Exception:
            pass

        # Setup Picamera2
        self.pi_cam = Picamera2()
        self.preview_config = None
        self.capture_config = None

        # Internal control
        self._running = False
        self._last_publish = 0.0

        # Configure camera at full-resolution preview
        self._init_camera()

        # Subscribe to capture event
        try:
            self.bus.subscribe("camera_capture", self.on_capture)
        except Exception:
            pass

    # ----------------------------------------
    def _init_camera(self):
        """Configure Picamera2 for preview at FULL resolution 2304x1296."""
        cfg = {"size": self.preview_res, "format": "RGB888"}
        self.preview_config = self.pi_cam.create_preview_configuration(main=cfg)

        self.capture_config = self.pi_cam.create_still_configuration(
            main={"size": self.capture_res, "format": "RGB888"}
        )

        self.pi_cam.configure(self.preview_config)
        self.pi_cam.start()

        print(f"[CameraHAL] Started preview at {self.preview_res} (RGB888), {self.fps} FPS cap.")

    # ----------------------------------------
    def get_frame(self):
        """Grab one preview frame in full resolution."""
        try:
            frame = self.pi_cam.capture_array("main")
            return frame
        except Exception as e:
            print(f"[CameraHAL] Error capturing preview frame: {e}")
            return None

    # ----------------------------------------
    async def update(self):
        """
        Preview loop: streams full-res frames at FPS cap.
        Publishes bus event: 'frame_ready'
        """
        self._running = True
        self._last_publish = 0.0

        while self._running:
            start = time.time()

            frame = self.get_frame()
            if frame is None:
                await asyncio.sleep(0.01)
                continue

            now = time.time()
            if now - self._last_publish >= self.frame_interval:
                # publish asynchronous
                try:
                    asyncio.create_task(self.bus.publish("frame_ready", {"frame": frame}))
                except Exception:
                    # fallback (await)
                    try:
                        await self.bus.publish("frame_ready", {"frame": frame})
                    except Exception:
                        pass

                self._last_publish = now

            # UI Preview (downscaled only for display)
            if self.show_preview:
                try:
                    edu_vis = getattr(self.state, "edu_preview_frame", None)

                    if (edu_vis is not None and
                        getattr(self.state, "current_system_mode", None) == "EducationMode"):
                        preview = cv2.resize(edu_vis, (960, 540))
                    else:
                        preview = cv2.resize(frame, (960, 540))

                    cv2.imshow("Camera Preview", preview)
                    cv2.waitKey(1)
                except Exception:
                    pass

            elapsed = time.time() - start
            to_sleep = max(0.0, self.frame_interval - elapsed)
            await asyncio.sleep(to_sleep)

    # ----------------------------------------
    async def on_capture(self, data):
        """
        On-demand capture: switches to 4608x2592 briefly,
        captures a still frame, then returns to preview resolution.
        """
        try:
            print("[CameraHAL] Capture requested — switching to capture resolution...")

            # Switch to capture config
            try:
                self.pi_cam.stop()
                self.pi_cam.configure(self.capture_config)
                self.pi_cam.start()
                await asyncio.sleep(0.25)
            except Exception as e:
                print(f"[CameraHAL] Warning: reconfigure failed: {e}")

            frame = None
            try:
                frame = self.pi_cam.capture_array("main")
            except Exception as e:
                print(f"[CameraHAL] Error capturing high-res frame: {e}")

            if frame is not None:
                try:
                    await self.bus.publish("camera_image_captured", {
                        "raw": frame,
                        "resolution": self.capture_res
                    })
                    print(f"[CameraHAL] Published captured image at {self.capture_res}")
                except Exception:
                    try:
                        asyncio.create_task(self.bus.publish(
                            "camera_image_captured",
                            {"raw": frame, "resolution": self.capture_res}
                        ))
                    except Exception:
                        pass
            else:
                print("[CameraHAL] Capture failed: no frame obtained.")

            # Switch back to preview
            try:
                self.pi_cam.stop()
                self.pi_cam.configure(self.preview_config)
                self.pi_cam.start()
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"[CameraHAL] Warning: could not return to preview config: {e}")

        except Exception as ex:
            print(f"[CameraHAL] Exception in on_capture: {ex}")

    # ----------------------------------------
    def stop(self):
        """Stop streaming and release camera."""
        self._running = False
        try:
            self.pi_cam.stop()
        except Exception:
            pass
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        print("[CameraHAL] Stopped camera.")

    # ----------------------------------------
    def release(self):
        self.stop()

