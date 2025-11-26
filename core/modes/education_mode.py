import cv2
import numpy as np
import asyncio


# ================================================================
# Simple 6D Pose Kalman Filter (Rvec/Tvec smoothing)
# ================================================================
class PoseKalman:
    def __init__(self):
        # State: [rx, ry, rz, tx, ty, tz]
        self.x = np.zeros((6,1))
        self.P = np.eye(6) * 1.0

        self.Q = np.eye(6) * 0.001      # process noise
        self.R = np.eye(6) * 0.01       # measurement noise

        self.initialized = False

    def update(self, rvec, tvec, confidence):
        if confidence <= 0:
            return self.x[0:3].copy(), self.x[3:6].copy()

        z = np.vstack([rvec.reshape(3,1), tvec.reshape(3,1)])
        H = np.eye(6)
        I = np.eye(6)

        if not self.initialized:
            self.x = z.copy()
            self.initialized = True
            return rvec, tvec

        # Prediction
        self.P = self.P + self.Q

        # Innovation
        y = z - H @ self.x
        S = H @ self.P @ H.T + self.R
        K = self.P @ H.T @ np.linalg.inv(S)

        # Update
        self.x = self.x + K @ y
        self.P = (I - K @ H) @ self.P

        # Output
        r = self.x[0:3].reshape(3,1)
        t = self.x[3:6].reshape(3,1)
        return r, t



# ================================================================
# EDUCATION MODE V4 — NO FINGER TRACKING
# ================================================================
class EducationMode:

    def __init__(self, bus, state):

        self.bus = bus
        self.state = state
        self.bus.subscribe("frame_ready", self.onFrame)

        # --------------------------------------------------------
        # Camera intrinsics (YOUR PI CAMERA V3 CALIBRATION)
        # --------------------------------------------------------
        self.K = np.array([
            [9.98753294e+02, 0.0,            1.15982896e+03],
            [0.0,            1.00373051e+03, 6.50888400e+02],
            [0.0,            0.0,            1.0]
        ], dtype=float)

        self.D = np.array([[-0.089, 0.142, -0.001, -0.002, -0.132]], dtype=float)

        # --------------------------------------------------------
        # Paper geometry (meters)
        # --------------------------------------------------------
        self.PAPER_W = 0.2159      # 8.5"
        self.PAPER_H = 0.2794      # 11"
        self.MARKER  = 0.0254      # 1"

        # --------------------------------------------------------
        # ARUCO DICTIONARY
        # --------------------------------------------------------
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(
            cv2.aruco.DICT_4X4_50
        )
        self.detector = cv2.aruco.ArucoDetector(
            self.aruco_dict,
            cv2.aruco.DetectorParameters()
        )

        # --------------------------------------------------------
        # Pose filtering + persistence
        # --------------------------------------------------------
        self.kalman = PoseKalman()
        self.last_rvec = None
        self.last_tvec = None

        # --------------------------------------------------------
        # Mouse debug
        # --------------------------------------------------------
        self.mouse_xy = (0,0)
        cv2.namedWindow("edu")
        cv2.setMouseCallback("edu", self._on_mouse)


    # =============================================================
    # Mouse handler
    # =============================================================
    def _on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_MOUSEMOVE:
            self.mouse_xy = (x, y)


    # =============================================================
    # Preprocessing (CLAHE + sharpen + bilateral)
    # =============================================================
    def preprocess(self, gray):
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8,8))
        g = clahe.apply(gray)

        # Sharpen
        blurred = cv2.GaussianBlur(g, (0,0), 1.0)
        sharp = cv2.addWeighted(g, 1.5, blurred, -0.5, 0)

        # Bilateral to keep edges clean
        filt = cv2.bilateralFilter(sharp, 7, 50, 50)

        return filt


    # =============================================================
    # Multi-scale marker detection (robust close-up)
    # =============================================================
    def detect_multiscale(self, gray):

        best_ids = None
        best_corners = None
        best_count = 0

        for scale in [1.0, 0.60, 0.40]:
            small = cv2.resize(gray, None, fx=scale, fy=scale)
            corners, ids, _ = self.detector.detectMarkers(small)

            if ids is None: 
                continue

            if len(ids) > best_count:
                best_count = len(ids)
                best_ids = ids
                best_corners = [
                    (c / scale) for c in corners
                ]

        return best_corners, best_ids


    # =============================================================
    # Define world coordinates for each marker's 4 corners
    # =============================================================
    def build_world_layout(self):
        M = self.MARKER
        W = self.PAPER_W
        H = self.PAPER_H

        return {
            0: [ [0,0], [M,0], [M,M], [0,M] ],                             # TL
            1: [ [W-M,0], [W,0], [W,M], [W-M,M] ],                         # TR
            3: [ [0,H-M], [M,H-M], [M,H], [0,H] ],                         # BL
            2: [ [W-M,H-M], [W,H-M], [W,H], [W-M,H] ]                      # BR
        }


    # =============================================================
    # Robust plane pose estimation
    # =============================================================
    def estimate_plane_pose(self, corners, ids):

        if ids is None or len(ids) == 0:
            return None, None, 0.0

        world_layout = self.build_world_layout()

        # Gather 3D-2D correspondences
        obj_pts = []
        img_pts = []

        for corner, mid in zip(corners, ids.flatten()):
            if mid not in world_layout:
                continue

            pts2d = corner.reshape(4,2)
            pts3d = world_layout[mid]

            for k in range(4):
                obj_pts.append([pts3d[k][0], pts3d[k][1], 0.0])
                img_pts.append([pts2d[k,0], pts2d[k,1]])

        obj_pts = np.array(obj_pts, float)
        img_pts = np.array(img_pts, float)

        # Marker count rules
        count = len(ids)

        if count >= 3:
            conf = 1.0
        elif count == 2:
            conf = 0.6
        elif count == 1:
            conf = 0.3
        else:
            return None, None, 0.0

        if count >= 2:
            ok, rvec, tvec = cv2.solvePnP(
                obj_pts, img_pts, self.K, self.D,
                flags=cv2.SOLVEPNP_ITERATIVE
            )
            if ok:
                return rvec, tvec, conf

        # 1 marker or fallback to last known
        if self.last_rvec is not None:
            return self.last_rvec, self.last_tvec, 0.2

        return None, None, 0.0


    # =============================================================
    # Pixel → World projection
    # =============================================================
    def pixel_to_world(self, px, py, rvec, tvec):

        invK = np.linalg.inv(self.K)
        uv = np.array([[px],[py],[1.0]])
        ray = invK @ uv
        ray /= np.linalg.norm(ray)

        R,_ = cv2.Rodrigues(rvec)
        cam_pos = -R.T @ tvec
        ray_world = R.T @ ray

        if abs(ray_world[2,0]) < 1e-9:
            return None

        lam = -cam_pos[2,0] / ray_world[2,0]
        Pw = cam_pos + lam * ray_world
        return Pw.reshape(3)


    # =============================================================
    # Frame handler
    # =============================================================
    async def onFrame(self, data):

        if self.state.current_system_mode != "EducationMode":
            return

        frame = data["frame"]
        disp = frame.copy()

        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        gray = self.preprocess(gray)

        # ------------------------------------------------------------
        # Multi-scale detection
        # ------------------------------------------------------------
        corners, ids = self.detect_multiscale(gray)

        if ids is None:
            print("VISIBLE: []")
            self.state.edu_preview_frame = disp
            return

        ids_list = ids.flatten().tolist()
        print("VISIBLE:", sorted(ids_list))

        # ------------------------------------------------------------
        # Compute plane pose (robust)
        # ------------------------------------------------------------
        rvec, tvec, conf = self.estimate_plane_pose(corners, ids)

        if rvec is None:
            print("No valid pose yet.")
            self.state.edu_preview_frame = disp
            return

        # ------------------------------------------------------------
        # Kalman filtering for rock-solid stability
        # ------------------------------------------------------------
        rvec_s, tvec_s = self.kalman.update(rvec, tvec, conf)
        self.last_rvec = rvec_s
        self.last_tvec = tvec_s

        R,_ = cv2.Rodrigues(rvec_s)

        # ------------------------------------------------------------
        # Paper outline projection
        # ------------------------------------------------------------
        paper = np.array([
            [0,0,0],
            [self.PAPER_W,0,0],
            [self.PAPER_W,self.PAPER_H,0],
            [0,self.PAPER_H,0]
        ], float)

        proj,_ = cv2.projectPoints(paper, rvec_s, tvec_s, self.K, self.D)
        proj = proj.reshape(-1,2).astype(int)

        cv2.polylines(disp, [proj], True, (0,255,0), 3)
        for p in proj:
            cv2.circle(disp, tuple(p), 6, (0,255,255), -1)

        # ------------------------------------------------------------
        # Debug: camera pose
        # ------------------------------------------------------------
        print("=== POSE ===")
        print("R:\n", R)
        print("t:\n", tvec_s.T)

        # ------------------------------------------------------------
        # Mouse → world
        # ------------------------------------------------------------
        mx,my = self.mouse_xy
        Pw = self.pixel_to_world(mx,my,rvec_s,tvec_s)

        if Pw is not None:
            txt = f"{Pw[0]:.3f}, {Pw[1]:.3f}"
            cv2.putText(disp, txt, (mx+10,my+10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0,255,0), 2)

        # ------------------------------------------------------------
        # Output frame to preview system
        # ------------------------------------------------------------
        self.state.edu_preview_frame = disp

