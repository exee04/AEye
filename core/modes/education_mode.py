import cv2
from ultralytics import YOLO
import os
import numpy as np
import asyncio

class EducationMode:
    TARGET_IDS = {1, 5}

    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.bus.subscribe("frame_ready", self.onFrame)
        self.bus.subscribe("enter_EducationMode", self.onEnter)
        self.bus.subscribe("button_press", self.captureFrame)

        self.frame = None
        self.debugFrame = None
        self.hasVisibleMarker = False
        self.captureFlag = False

        # --- ArUco Setup ---
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)

        # --- Camera Calibration Values ---
        self.camera_matrix = np.array([
            [9.98753294e+02, 0.0, 1.15982896e+03],
            [0.0, 1.00373051e+03, 6.50888400e+02],
            [0.0, 0.0, 1.0]
        ])
        self.dist_coeffs = np.array([[-0.05798983, 0.13855422, 0.00113712, 0.00015827, -0.09092239]])

        # --- Marker Parameters ---
        self.marker_length = 0.02  # 2 cm = 0.02 m

    async def onFrame(self, data):
        if self.state.current_system_mode != "EducationMode":
            return

        if not self.state.hasConnection:
            await self.offlineCamera(data)
            return

        if self.state.hasBraillePaper:
            return

        self.frame = data.get("frame")
        self.debugFrame = self.frame.copy()

        # Detect ArUco markers
        corners, ids, _ = self.detector.detectMarkers(self.debugFrame)

        if ids is not None:
            ids = ids.flatten()
            for i, marker_id in enumerate(ids):
                if marker_id in self.TARGET_IDS:
                    cv2.aruco.drawDetectedMarkers(self.frame, [corners[i]], np.array([[ids[i]]]))
                    self.hasVisibleMarker = True
                    print(f"[OK] Found target marker ID: {marker_id}")

                    # --- Pose Estimation ---
                    obj_points = np.array([
                        [-self.marker_length / 2,  self.marker_length / 2, 0],
                        [ self.marker_length / 2,  self.marker_length / 2, 0],
                        [ self.marker_length / 2, -self.marker_length / 2, 0],
                        [-self.marker_length / 2, -self.marker_length / 2, 0]
                    ], dtype=np.float32)

                    img_points = corners[i][0].astype(np.float32)

                    success, rvec, tvec = cv2.solvePnP(
                        obj_points,
                        img_points,
                        self.camera_matrix,
                        self.dist_coeffs
                    )
                    if success:
                        cv2.drawFrameAxes(self.frame, self.camera_matrix, self.dist_coeffs, rvec, tvec, 0.01)

                        # Example 3D points in marker space (Braille dots)
                        braille_points_3d = np.array([
                            [0.03,  0.02, 0],
                            [0.04,  0.01, 0],
                            [0.05,  0.00, 0],
                            [0.03, -0.01, 0]
                        ], dtype=np.float32)

                        # Project to image space
                        img_points, _ = cv2.projectPoints(
                            braille_points_3d,
                            rvec,
                            tvec,
                            self.camera_matrix,
                            self.dist_coeffs
                        )

                        # Draw projected points
                        for p in img_points:
                            x, y = int(p[0][0]), int(p[0][1])
                            cv2.circle(self.frame, (x, y), 4, (0, 0, 255), -1)

                    return  # stop after first valid marker

        self.hasVisibleMarker = False

    async def captureFrame(self, data):
        if self.state.current_system_mode != "EducationMode":
            return

        pin = data.get("pin")
        if pin == 24:
            if self.captureFlag:
                return
            if not self.state.hasConnection:
                print("[EducationMode] You need an internet connection to scan the paper")
                return
            if self.state.hasBraillePaper:
                print("There is already a paper")
                return
            if not self.hasVisibleMarker:
                print("Braille paper with the marker must be visible")
                return

            self.captureFlag = True
            for i in range(3, 0, -1):
                print(f"Capturing in {i}...")
                await asyncio.sleep(1)

            print("[Camera] Capturing frame...")
            await self.bus.publish("camera_capture", {})
            self.captureFlag = False

    async def onEnter(self):
        return

    async def offlineCamera(self, data):
        print("Offline Cam")
        return

