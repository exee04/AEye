import cv2
import numpy as np
class EducationMode:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.bus.subscribe("frame_ready", self.onFrame)
        self.bus.subscribe("enter_EducationMode", self.onEnter)

        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)

    async def onFrame(self, data):
        if self.state.current_system_mode != "EducationMode":
            return
        if not self.state.hasConnection:
            await self.offlineCamera(data)
            return
        print("Online cam")
        frame = data.get("frame")
        

    async def onEnter(self):
        return

    async def offlineCamera(self, data):
        print("Offline Cam")
        return

