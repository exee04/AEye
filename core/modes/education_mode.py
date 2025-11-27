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
# import cv2
import numpy as np
import asyncio

class EducationMode:

    # ======================================================================
    # INIT
    # ======================================================================
    def __init__(self, bus, state):

        self.bus = bus
        self.state = state
        self.bus.subscribe("frame_ready", self.onFrame)

        # ===============================================================
        # CAMERA CALIBRATION (2304x1296)
        # ===============================================================
        self.K = np.array([
            [9.98753294e+02, 0.0,            1.15982896e+03],
            [0.0,            1.00373051e+03, 6.50888400e+02],
            [0.0,            0.0,            1.0]
        ], dtype=float)

        self.D = np.array([[-0.089, 0.142, -0.001, -0.002, -0.132]], dtype=float)

        # ===============================================================
        # PAPER GEOMETRY (meters) — 8.5 x 11 inch LINEN PAPER
        # ===============================================================
        self.PAPER_W = 0.2159    # 8.5"
        self.PAPER_H = 0.2794    # 11"
        self.MARKER  = 0.0254    # 1"

        # ===============================================================
        # ARUCO DETECTOR
        # ===============================================================
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        params = cv2.aruco.DetectorParameters()

        # Robustness improvements
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        params.cornerRefinementMaxIterations = 30
        params.cornerRefinementWinSize = 5

        params.adaptiveThreshWinSizeMin = 5
        params.adaptiveThreshWinSizeMax = 25
        params.adaptiveThreshWinSizeStep = 5

        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, params)

        # ===============================================================
        # SMOOTHING (EMA)
        # ===============================================================
        self.alpha = 0.15
        self.rvec_f = None
        self.tvec_f = None

        # ===============================================================
        # MOUSE
        # ===============================================================
        self.mouse_xy = (0,0)
        cv2.namedWindow("Camera Preview")
        cv2.setMouseCallback("Camera Preview", self._on_mouse)

        # ===============================================================
        # HARDCODED REGIONS (Letter interaction boxes)
        # Coordinates in PAPER WORLD SPACE (meters)
        # ===============================================================
        self.regions = [
            {"label": "A", "x": 0.02, "y": 0.03, "w": 0.03, "h": 0.03},
            {"label": "B", "x": 0.07, "y": 0.03, "w": 0.03, "h": 0.03},
            {"label": "C", "x": 0.12, "y": 0.03, "w": 0.03, "h": 0.03},
        ]

    # ======================================================================
    # MOUSE CALLBACK
    # ======================================================================
    def _on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_MOUSEMOVE:
            # Convert from preview size back to full resolution
            scale_x = 2304 / 960
            scale_y = 1296 / 540

            self.mouse_xy = (int(x * scale_x), int(y * scale_y))
    # ======================================================================
    # UNDISTORT CORNERS
    # ======================================================================
    def undistort(self, corners4):
        pts = corners4.reshape(-1,1,2).astype(np.float32)
        und = cv2.undistortPoints(pts, self.K, self.D, None, self.K)
        return und.reshape(4,2)

    # ======================================================================
    # PIXEL → WORLD (Plane Z=0)
    # ======================================================================
    def pixel_to_world(self, px, py, rvec, tvec):

        invK = np.linalg.inv(self.K)
        uv1 = np.array([[px],[py],[1.0]])
        ray_cam = invK @ uv1
        ray_cam /= np.linalg.norm(ray_cam)

        R,_ = cv2.Rodrigues(rvec)
        cam_pos = -R.T @ tvec
        ray_world = R.T @ ray_cam

        if abs(ray_world[2,0]) < 1e-8:
            return None

        lam = -cam_pos[2,0] / ray_world[2,0]
        Pw = cam_pos + lam * ray_world
        return Pw.reshape(3)

    # ======================================================================
    # REGION HIT TEST
    # ======================================================================
    def check_region_hit(self, x, y):
        for region in self.regions:
            rx, ry = region["x"], region["y"]
            rw, rh = region["w"], region["h"]

            if (x >= rx and x <= rx+rw and
                y >= ry and y <= ry+rh):
                return region["label"]
        return None

    # ======================================================================
    # PREPROCESS GRAY FOR DETECTION
    # ======================================================================
    def preprocess_gray(self, gray):
        blur = cv2.GaussianBlur(gray, (5,5), 0)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4,4))
        eq = clahe.apply(blur)
        return eq

    # ======================================================================
    # MAIN FRAME
    # ======================================================================
    async def onFrame(self, data):

        if self.state.current_system_mode != "EducationMode":
            return

        frame = data["frame"]
        disp  = frame.copy()

        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        gray = self.preprocess_gray(gray)

        # --------------------------------------------------------------
        # DETECT MARKERS
        # --------------------------------------------------------------
        corners, ids, _ = self.detector.detectMarkers(gray)

        if ids is None:
            print("Visible markers: []")
            self.state.edu_preview_frame = disp
            return

        ids = ids.flatten().tolist()
        print("Visible markers:", ids)

        # Require ALL FOUR corners for strongest stability
        required = {0,1,2,3}
        if not required.issubset(ids):
            cv2.putText(disp, "Need markers 0,1,2,3", (40,40),
                        cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)
            self.state.edu_preview_frame = disp
            return

        # --------------------------------------------------------------
        # BUILD MATCHED POINT SET
        # --------------------------------------------------------------
        obj_pts = []
        img_pts = []

        # World layout
        layout = {
            0: [  # TL
                [0,0],
                [self.MARKER,0],
                [self.MARKER,self.MARKER],
                [0,self.MARKER]
            ],
            1: [  # TR
                [self.PAPER_W-self.MARKER,0],
                [self.PAPER_W,0],
                [self.PAPER_W,self.MARKER],
                [self.PAPER_W-self.MARKER,self.MARKER]
            ],
            3: [  # BL
                [0,self.PAPER_H-self.MARKER],
                [self.MARKER,self.PAPER_H-self.MARKER],
                [self.MARKER,self.PAPER_H],
                [0,self.PAPER_H]
            ],
            2: [  # BR
                [self.PAPER_W-self.MARKER,self.PAPER_H-self.MARKER],
                [self.PAPER_W,self.PAPER_H-self.MARKER],
                [self.PAPER_W,self.PAPER_H],
                [self.PAPER_W-self.MARKER,self.PAPER_H]
            ]
        }

        # Extract and add all matched correspondences
        for i, mid in enumerate(ids):
            if mid not in required:
                continue

            raw = corners[i].reshape(4,2)
            und = self.undistort(raw)

            for k in range(4):
                obj_pts.append([layout[mid][k][0],
                                layout[mid][k][1],
                                0.0])
                img_pts.append([und[k,0], und[k,1]])

        obj_pts = np.array(obj_pts, dtype=float)
        img_pts = np.array(img_pts, dtype=float)

        # --------------------------------------------------------------
        # SOLVE PnP
        # --------------------------------------------------------------
        ok, rvec, tvec = cv2.solvePnP(
            obj_pts, img_pts,
            self.K, self.D,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        if not ok:
            print("solvePnP FAILED")
            self.state.edu_preview_frame = disp
            return

        # Smooth
        rvec_s = rvec if self.rvec_f is None else self.alpha*rvec + (1-self.alpha)*self.rvec_f
        tvec_s = tvec if self.tvec_f is None else self.alpha*tvec + (1-self.alpha)*self.tvec_f
        self.rvec_f = rvec_s
        self.tvec_f = tvec_s

        # --------------------------------------------------------------
        # DRAW PAPER OUTLINE
        # --------------------------------------------------------------
        paper = np.array([
            [0,0,0],
            [self.PAPER_W,0,0],
            [self.PAPER_W,self.PAPER_H,0],
            [0,self.PAPER_H,0]
        ],float)

        proj,_ = cv2.projectPoints(paper, rvec_s, tvec_s, self.K, self.D)
        pts = proj.reshape(-1,2).astype(int)

        cv2.polylines(disp, [pts], True, (0,255,0), 3)
        for p in pts:
            cv2.circle(disp, tuple(p), 6, (0,255,255), -1)

        # --------------------------------------------------------------
        # DRAW INTERACTION REGIONS
        # --------------------------------------------------------------
        for reg in self.regions:
            x,y,w,h = reg["x"], reg["y"], reg["w"], reg["h"]

            box = np.array([
                [x,    y,    0],
                [x+w,  y,    0],
                [x+w,  y+h,  0],
                [x,    y+h,  0]
            ],float)

            proj,_ = cv2.projectPoints(box, rvec_s, tvec_s, self.K, self.D)
            p2 = proj.reshape(-1,2).astype(int)

            cv2.polylines(disp, [p2], True, (0,128,255), 2)
            cv2.putText(disp, reg["label"],
                        (p2[0][0], p2[0][1]-5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0,128,255), 2)

        # --------------------------------------------------------------
        # MOUSE → WORLD PROJECTION
        # --------------------------------------------------------------
        mx,my = self.mouse_xy
        Pw = self.pixel_to_world(mx,my, rvec_s, tvec_s)

        if Pw is not None:
            Xw, Yw, Zw = Pw
            cv2.putText(disp, f"{Xw:.3f},{Yw:.3f}",
                        (mx+10,my+10),
                        cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,255,0),2)

            hit = self.check_region_hit(Xw, Yw)
            if hit:
                print(f"Mouse is touching {hit}")

        # --------------------------------------------------------------
        # OUTPUT
        # --------------------------------------------------------------
        self.state.edu_preview_frame = disp
