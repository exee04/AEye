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
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)
        self.hasVisibleMarker = False
        self.captureFlag = False

    async def onFrame(self, data):
        if self.state.current_system_mode != "EducationMode":
            return
        if not self.state.hasConnection:
            await self.offlineCamera(data)
            return
        if self.state.hasBraillePaper:
            return

        self.frame = data.get("frame")
        self.debugFrame = data.get("frame").copy()
        corners, ids, _ = self.detector.detectMarkers(self.debugFrame)

        if ids is not None:
            ids = ids.flatten()
            for i, marker_id in enumerate(ids):
                if marker_id == 5:
                    cv2.aruco.drawDetectedMarkers(self.debugFrame, [corners[i]], np.array([[ids[i]]]))
                    self.hasVisibleMarker = True
                    print(f"[OK] Found target marker ID: {marker_id}")
                    return
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
            PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            CACHE_DIR = os.path.join(PROJECT_ROOT, "cache")
            os.makedirs(CACHE_DIR, exist_ok=True)

            raw_path = os.path.join(CACHE_DIR, "1_raw.jpg")
            cv2.imwrite(raw_path, self.frame)
            print(f"[Camera] Saved raw frame to {raw_path}")
            self.captureFlag = False

    async def onEnter(self):
        return

    async def offlineCamera(self, data):
        print("Offline Cam")
        return
