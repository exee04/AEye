import cv2
import numpy as np
import asyncio


# ================================================================
#  POSE KALMAN FILTER
# ================================================================
class PoseKalman:
    def __init__(self):
        self.x = np.zeros((6,1))
        self.P = np.eye(6) * 1.0
        self.Q = np.eye(6) * 0.0008
        self.R = np.eye(6) * 0.01
        self.initialized = False

    def update(self, rvec, tvec, confidence):

        if confidence <= 0:
            return self.x[:3].copy(), self.x[3:].copy()

        z = np.vstack([rvec.reshape(3,1), tvec.reshape(3,1)])
        H = np.eye(6)
        I = np.eye(6)

        if not self.initialized:
            self.x = z.copy()
            self.initialized = True
            return rvec, tvec

        self.P = self.P + self.Q
        y = z - H @ self.x
        S = H @ self.P @ H.T + self.R
        K = self.P @ H.T @ np.linalg.inv(S)

        self.x = self.x + K @ y
        self.P = (I - K @ H) @ self.P

        return self.x[:3].reshape(3,1), self.x[3:].reshape(3,1)



# ================================================================
#  EDUCATION MODE V8 — FIXED MARKER LAYOUT + FINGER TIP
# ================================================================
class EducationMode:

    def __init__(self, bus, state):

        self.bus = bus
        self.state = state
        self.bus.subscribe("frame_ready", self.onFrame)

        # CAMERA INTRINSICS (2304×1296)
        self.K = np.array([
            [9.98753294e+02, 0.0,            1.15982896e+03],
            [0.0,            1.00373051e+03, 6.50888400e+02],
            [0.0,            0.0,            1.0]
        ], float)

        self.D = np.array([[-0.089, 0.142, -0.001, -0.002, -0.132]], float)

        # PAPER GEOMETRY
        self.PAPER_W = 0.2159
        self.PAPER_H = 0.2794
        self.MARKER  = 0.0254

        # FINGER MARKER
        self.FINGER_ID = 17
        self.FINGER_MARKER_SIZE = 0.0127
        self.FINGERTIP_FORWARD = 0.015
        self.FINGERTIP_DOWN = 0.004

        self.PAPER_MARKERS = {0,1,2,3}

        # ARUCO DETECTOR
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(
            cv2.aruco.DICT_4X4_50
        )
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        params.cornerRefinementMaxIterations = 40
        params.cornerRefinementWinSize = 5
        params.adaptiveThreshWinSizeMin = 5
        params.adaptiveThreshWinSizeMax = 45
        params.adaptiveThreshWinSizeStep = 5

        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, params)

        # PAPER POSE KALMAN FILTER
        self.kalman = PoseKalman()

        # UI (mouse)
        self.mouse_xy = (0,0)
        cv2.namedWindow("Camera Preview")
        cv2.setMouseCallback("Camera Preview", self._on_mouse)

        # INTERACTION POINTS (CIRCLES)
        self.regions = [
            {"label": "A","x": 0.0406,"y": 0.0500, "r": 0.015},
            {"label": "B","x": 0.0522,"y": 0.0500, "r": 0.015},
            {"label": "C","x": 0.0559,"y": 0.0500, "r": 0.015},
            {"label": "D","x": 0.0608,"y": 0.0645, "r": 0.015},
            {"label": "E","x": 0.0758,"y": 0.1150, "r": 0.015},
        ]


    # ===============================================================
    def _on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_MOUSEMOVE:
            self.mouse_xy = (int(x * 2304/960), int(y * 1296/540))


    # ===============================================================
    def preprocess_gray(self, gray):
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(6,6))
        gray = clahe.apply(gray)
        gray = cv2.GaussianBlur(gray, (3,3), 0)
        return gray


    # ===============================================================
    def undistort(self, corners):
        pts = corners.reshape(-1,1,2).astype(np.float32)
        und = cv2.undistortPoints(pts, self.K, self.D, None, self.K)
        return und.reshape(4,2)


    # ===============================================================
    def detect_multiscale(self, gray):
        best = {"ids":None, "corners":None, "score":-1}

        for scale in [1.0, 0.75, 0.5]:
            small = cv2.resize(gray, None, fx=scale, fy=scale)
            corners, ids, _ = self.detector.detectMarkers(small)

            if ids is None:
                continue

            ids_list = ids.flatten().tolist()
            score = sum(1 for i in ids_list if i in self.PAPER_MARKERS) * 10 + len(ids_list)

            if score > best["score"]:
                best["score"] = score
                best["ids"] = ids
                best["corners"] = [c / scale for c in corners]

        return best["corners"], best["ids"]


    # ===============================================================
    def check_region_hit_circle(self, x, y):
        for reg in self.regions:
            dx = x - reg["x"]
            dy = y - reg["y"]
            if dx*dx + dy*dy <= reg["r"]*reg["r"]:
                return reg["label"]
        return None


    # ===============================================================
    async def onFrame(self, data):
        if self.state.current_system_mode != "EducationMode":
            return

        frame = data["frame"]
        disp = frame.copy()

        gray = self.preprocess_gray(
            cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        )

        # -----------------------------------------
        # MULTISCALE ARUCO DETECTION
        # -----------------------------------------
        corners, ids = self.detect_multiscale(gray)
        if ids is None:
            self.state.edu_preview_frame = disp
            return

        ids_list = ids.flatten().tolist()

        paper = []
        finger = None

        for i, mid in enumerate(ids_list):
            if mid in self.PAPER_MARKERS:
                paper.append((mid, corners[i].reshape(4,2)))
            elif mid == self.FINGER_ID:
                finger = corners[i].reshape(4,2)

        # -----------------------------------------
        # REQUIRE AT LEAST TWO PAPER MARKERS
        # -----------------------------------------
        if len(paper) < 2:
            self.state.edu_preview_frame = disp
            return

        # -----------------------------------------
        # CORRECT MARKER LAYOUT (0,1,2,3 clockwise)
        # -----------------------------------------
        layout = {
            0: [[0,0],
                [self.MARKER,0],
                [self.MARKER,self.MARKER],
                [0,self.MARKER]],

            1: [[self.PAPER_W-self.MARKER,0],
                [self.PAPER_W,0],
                [self.PAPER_W,self.MARKER],
                [self.PAPER_W-self.MARKER,self.MARKER]],

            2: [[0,self.PAPER_H-self.MARKER],
                [self.MARKER,self.PAPER_H-self.MARKER],
                [self.MARKER,self.PAPER_H],
                [0,self.PAPER_H]],

            3: [[self.PAPER_W-self.MARKER,self.PAPER_H-self.MARKER],
                [self.PAPER_W,self.PAPER_H-self.MARKER],
                [self.PAPER_W,self.PAPER_H],
                [self.PAPER_W-self.MARKER,self.PAPER_H]]
        }


        # -----------------------------------------
        # BUILD PNP CORRESPONDENCES
        # -----------------------------------------
        obj_pts = []
        img_pts = []

        for mid, raw in paper:
            und = self.undistort(raw)
            for k in range(4):
                obj_pts.append([layout[mid][k][0], layout[mid][k][1], 0])
                img_pts.append([und[k,0], und[k,1]])

        obj_pts = np.array(obj_pts, float)
        img_pts = np.array(img_pts, float)

        ok, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, self.K, self.D)
        if not ok:
            self.state.edu_preview_frame = disp
            return

        rvec_s, tvec_s = self.kalman.update(rvec, tvec, len(paper)/4)

        R_paper,_ = cv2.Rodrigues(rvec_s)
        t_paper = tvec_s.reshape(3)

        # -----------------------------------------
        # DRAW PAPER
        # -----------------------------------------
        paper3d = np.array([
            [0,0,0],
            [self.PAPER_W,0,0],
            [self.PAPER_W,self.PAPER_H,0],
            [0,self.PAPER_H,0]
        ], float)

        proj,_ = cv2.projectPoints(paper3d, rvec_s, tvec_s, self.K, self.D)
        cv2.polylines(disp, [proj.reshape(-1,2).astype(int)], True, (0,255,0), 3)

        # -----------------------------------------
        # DRAW CIRCULAR REGIONS
        # -----------------------------------------
        for reg in self.regions:
            center = np.array([[reg["x"], reg["y"], 0]], float)
            proj_c,_ = cv2.projectPoints(center, rvec_s, tvec_s, self.K, self.D)
            cx,cy = proj_c.reshape(2).astype(int)

            cv2.circle(disp, (cx,cy), 14, (0,128,255), 2)
            cv2.putText(disp, reg["label"], (cx+5,cy-5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,128,255),2)

        fingertip_world = None

        # -----------------------------------------
        # FINGER MARKER → FINGERTIP COMPUTATION
        # -----------------------------------------
        if finger is not None:

            und_f = self.undistort(finger)

            L = self.FINGER_MARKER_SIZE
            obj_f = np.array([
                [-L/2,  L/2, 0],
                [ L/2,  L/2, 0],
                [ L/2, -L/2, 0],
                [-L/2, -L/2, 0]
            ])

            ok_f, rvec_f, tvec_f = cv2.solvePnP(obj_f, und_f, self.K, self.D,
                                                flags=cv2.SOLVEPNP_IPPE_SQUARE)

            if ok_f:
                Rf,_ = cv2.Rodrigues(rvec_f)
                Tf = tvec_f.reshape(3)

                forward = Rf[:,1]
                downward = -Rf[:,2]

                fingertip_cam = (
                    Tf
                    + forward * self.FINGERTIP_FORWARD
                    + downward * self.FINGERTIP_DOWN
                )

                fingertip_world = R_paper.T @ (fingertip_cam - t_paper)

                Fx,Fy,Fz = fingertip_world
                print(f"[FINGER XYZ on paper] {Fx:.4f}, {Fy:.4f}, {Fz:.4f}")

                # Draw fingertip
                fp = fingertip_cam.reshape(1,1,3)
                proj_ft,_ = cv2.projectPoints(fp, np.zeros((3,1)), np.zeros((3,1)),
                                              self.K, self.D)
                cv2.circle(disp, tuple(proj_ft.reshape(2).astype(int)), 10, (255,0,0), -1)

        # -----------------------------------------
        # HIT-TEST FROM FINGER
        # -----------------------------------------
        if fingertip_world is not None:
            Fx,Fy,Fz = fingertip_world
            hit = self.check_region_hit_circle(Fx, Fy)
            if hit:
                print(f"[FINGER TOUCH] {hit}")

        self.state.edu_preview_frame = disp



    # ===============================================================
    # PIXEL → PAPER
    # ===============================================================
    def _pixel_to_paper(self, px, py, R_paper, t_paper):

        uv1 = np.array([px,py,1.0])
        ray_cam = np.linalg.inv(self.K) @ uv1
        ray_cam /= np.linalg.norm(ray_cam)

        cam_pos = -R_paper.T @ t_paper
        ray_world = R_paper.T @ ray_cam

        if abs(ray_world[2]) < 1e-8:
            return None

        lam = -cam_pos[2] / ray_world[2]
        return cam_pos + lam * ray_world

