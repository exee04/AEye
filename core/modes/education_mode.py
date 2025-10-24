import cv2
import numpy as np
import asyncio
import os
from .braille_overlay import BrailleOverlayHandler

class EducationMode:
    TARGET_IDS = {1, 5}

    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.bus.subscribe("frame_ready", self.onFrame)
        self.bus.subscribe("enter_EducationMode", self.onEnter)
        self.bus.subscribe("button_press", self.captureFrame)

        # marker physical size (1 inch)
        self.marker_size_m = 0.0254

        # camera intrinsics will be set from SystemState; fallback later if needed
        self.cam_w = getattr(self.state, "cam_width", None)
        self.cam_h = getattr(self.state, "cam_height", None)
        self.fov = 120.0  # degrees fallback

        # aruco detector (modern API)
        self.detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))
        self.frame = None
        self.debugFrame = None

        # braille overlay instance
        self.braille = BrailleOverlayHandler(camera_matrix=None, dist_coeffs=None, marker_size_m=self.marker_size_m)
        # set intrinsics if we have them now (otherwise we'll set on first frame)
        if self.cam_w and self.cam_h:
            self.braille.set_camera_intrinsics(self.cam_w, self.cam_h, fov_deg=self.fov)

        # load layout (expect mm-based JSON)
        layout_path = os.path.join(os.path.dirname(__file__), "offline_braille_map.json")
        self.braille.load_braille_layout(layout_path)

        # smoothing state (for filtering in EducationMode when needed)
        # but most smoothing is inside BrailleOverlayHandler
        self.prev_detection_time = 0.0

        # register mouse callback (CameraHAL uses window name "Camera Preview")
        try:
            cv2.setMouseCallback("Camera Preview", self.braille.on_mouse_move)
        except Exception:
            pass

    # Helper: pose estimator using solvePnP (works with ArucoDetector corners)
    def estimate_pose_from_corners(self, marker_corners):
        """
        marker_corners: array like shape (1,4,2) or (4,2)
        returns rvec (3,), tvec (3,) in meters
        """
        c = np.asarray(marker_corners).reshape(4, 2).astype(np.float32)

        half = self.marker_size_m / 2.0
        obj_points = np.array([
            [-half,  half, 0.0],
            [ half,  half, 0.0],
            [ half, -half, 0.0],
            [-half, -half, 0.0]
        ], dtype=np.float32)

        # ensure camera intrinsics exist
        if self.braille.camera_matrix is None:
            # fallback to estimate from state or use default
            cam_w = getattr(self.state, "cam_width", 1536)
            cam_h = getattr(self.state, "cam_height", 864)
            self.braille.set_camera_intrinsics(cam_w, cam_h, fov_deg=self.fov)

        success, rvec, tvec = cv2.solvePnP(obj_points, c, self.braille.camera_matrix, self.braille.dist_coeffs)
        if not success:
            return None, None
        return rvec.reshape(3), tvec.reshape(3)

    async def onFrame(self, data):
        if self.state.current_system_mode != "EducationMode":
            return

        frame = data.get("frame")
        if frame is None:
            return

        self.frame = frame
        self.debugFrame = frame.copy()

        # aruco detect
        corners, ids, _ = self.detector.detectMarkers(self.frame)
        detected = False
        if ids is not None:
            ids = ids.flatten()
            for i, marker_id in enumerate(ids):
                if marker_id in self.TARGET_IDS:
                    marker_corners = corners[i]
                    # estimate pose
                    rvec, tvec = self.estimate_pose_from_corners(marker_corners)
                    if rvec is None or tvec is None:
                        continue

                    # center pixel for convenience
                    center_px = tuple(np.mean(marker_corners.reshape(-1, 2), axis=0).astype(int))

                    # update filtered pose inside braille handler (robust)
                    self.braille.update_pose_filtered(rvec, tvec)

                    # draw debug outlines & axes (use filtered pose if available)
                    cv2.aruco.drawDetectedMarkers(self.debugFrame, [marker_corners])
                    # draw axes using the smoothed pose for visual stability
                    if self.braille._pose_initialized:
                        try:
                            cv2.drawFrameAxes(self.debugFrame,
                                              self.braille.camera_matrix,
                                              self.braille.dist_coeffs,
                                              self.braille._rvec.reshape(3,1).astype(np.float32),
                                              self.braille._tvec_filt.reshape(3,1).astype(np.float32),
                                              self.marker_size_m * 0.5)
                        except Exception:
                            pass

                    detected = True
                    break

        # If we have a filtered pose, draw the braille overlay anchored to it
        if self.braille._pose_initialized:
            self.debugFrame = self.braille.draw(self.debugFrame)

        # show debug
        self.frame = self.debugFrame

    async def captureFrame(self, data):
        # preserve your existing capture behavior - simplified here
        pin = data.get("pin")
        if pin != 24:
            return
        # implement your capture conditions
        if not getattr(self.state, "hasConnection", True):
            print("[EducationMode] Need internet to capture (scan) paper.")
            return
        if not self.braille._pose_initialized:
            print("[EducationMode] Marker not visible / pose not initialized.")
            return

        print("[Camera] Saving capture...")
        PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        CACHE_DIR = os.path.join(PROJECT_ROOT, "cache")
        os.makedirs(CACHE_DIR, exist_ok=True)
        raw_path = os.path.join(CACHE_DIR, "1_raw.jpg")
        cv2.imwrite(raw_path, self.frame)
        print("[Camera] Saved", raw_path)

    async def onEnter(self):
        # reload layout if resolution changed
        cam_w = getattr(self.state, "cam_width", None)
        cam_h = getattr(self.state, "cam_height", None)
        if cam_w and cam_h:
            self.braille.set_camera_intrinsics(cam_w, cam_h, fov_deg=self.fov)

        layout_path = os.path.join(os.path.dirname(__file__), "offline_braille_map.json")
        self.braille.load_braille_layout(layout_path)

    async def offlineCamera(self, data):
        # fallback when offline - you can show a static UI or similar
        print("Offline Cam")
        return

