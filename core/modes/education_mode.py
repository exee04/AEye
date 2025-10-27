import cv2
import json
import numpy as np
import asyncio
import os

# --- Calibration (From your provided parameters) ---
CAMERA_MATRIX = np.array([
    [9.98753294e+02, 0.0, 1.15982896e+03],
    [0.0, 1.00373051e+03, 6.50888400e+02],
    [0.0, 0.0, 1.0]
])
DIST_COEFFS = np.array([[-0.05798983, 0.13855422, 0.00113712, 0.00015827, -0.09092239]])

# --- ArUco setup ---
ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ARUCO_PARAMS = cv2.aruco.DetectorParameters()
class EducationMode:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.bus.subscribe("frame_ready", self.onFrame)



    def load_offline_data(path="offline_braille.json"):
        if not os.path.exists(path):
            print(f"[EducationMode] ❌ Missing {path}")
            return None
        with open(path, "r") as f:
            data = json.load(f)
        print(f"[EducationMode] ✅ Loaded {path}")
        return data


    async def onEnter(data, state, bus):
        """Called when entering EducationMode."""
        state.current_system_mode = "EducationMode"
        await bus.publish("tts", {"text": "Entering Education Mode"})
        print("[EducationMode] Started in offline mode")
        return


    async def onFrame(self, data):
        """Main EducationMode loop — runs on each frame."""
        if self.state.current_system_mode != "EducationMode":
            return

        frame = data.get("frame")
        if frame is None:
            return

        # --- Step 1: Undistort frame ---
        undistorted = cv2.undistort(frame, CAMERA_MATRIX, DIST_COEFFS)

        # --- Step 2: Detect ArUco markers ---
        corners, ids, _ = cv2.aruco.detectMarkers(undistorted, ARUCO_DICT, parameters=ARUCO_PARAMS)

        if ids is None:
            self.state.hasBraillePaper = False
            return

        ids = ids.flatten()
        output = undistorted.copy()

        # --- Step 3: Identify base marker and interaction marker ---
        base_marker_id = None
        finger_marker_id = None
        base_center = None
        finger_center = None

        # You can choose fixed IDs (e.g., 0 for paper, 1 for finger)
        for i, marker_id in enumerate(ids):
            pts = corners[i][0]
            center = np.mean(pts, axis=0).astype(int)
            cv2.polylines(output, [pts.astype(int)], True, (0, 255, 0), 2)
            cv2.putText(output, f"ID:{marker_id}", tuple(center), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

            if marker_id == 0:
                base_marker_id = marker_id
                base_center = center
            elif marker_id == 1:
                finger_marker_id = marker_id
                finger_center = center

        if base_marker_id is None:
            # No base marker detected → skip frame
            return

        self.state.hasBraillePaper = True

        # --- Step 4: Load offline mapping once ---
        if not hasattr(self, self.state, "braille_data"):
            self.state.braille_data = self.load_offline_data()

        if not self.state.braille_data:
            return

        # --- Step 5: Compute scaling based on resolution ---
        src_w, src_h = 640, 480
        cur_w, cur_h = self.state.cam_width or 2304, self.state.cam_height or 1296
        scale_x = cur_w / src_w
        scale_y = cur_h / src_h

        # --- Step 6: Draw Braille boxes relative to detected base marker ---
        base_ref = np.array(self.state.braille_data["base_marker_center"])
        offset = (base_center - base_ref * [scale_x, scale_y]).astype(int)

        touched_label = None
        for braille in self.state.braille_data["braille_positions"]:
            label = braille["label"]
            rel_x, rel_y = braille["relative"]
            size_x, size_y = braille["size"]

            abs_x = int(base_center[0] + (rel_x * scale_x))
            abs_y = int(base_center[1] + (rel_y * scale_y))

            x1, y1 = abs_x - int(size_x * scale_x // 2), abs_y - int(size_y * scale_y // 2)
            x2, y2 = abs_x + int(size_x * scale_x // 2), abs_y + int(size_y * scale_y // 2)

            color = (255, 0, 0)
            if finger_center is not None:
                if x1 <= finger_center[0] <= x2 and y1 <= finger_center[1] <= y2:
                    color = (0, 255, 255)
                    touched_label = label

            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
            cv2.putText(output, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        # --- Step 7: If user touches a Braille letter ---
        if touched_label:
            if getattr(self.state, "last_spoken", None) != touched_label:
                await self.bus.publish("tts", {"text": f"{touched_label}"})
                self.state.last_spoken = touched_label

        # --- Step 8: Show debug preview ---
        self.state.edu_frame = cv2.resize(output, (640, 360))
        cv2.imshow("Education Mode", self.state.edu_frame)
        cv2.waitKey(1)

