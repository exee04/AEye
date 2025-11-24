import cv2
from ultralytics import YOLO
import numpy as np
import asyncio
import os
import glob
from collections import defaultdict

class EducationMode:
    TARGET_IDS = {1, 5}
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CAPTURE_DIR = os.path.join(PROJECT_ROOT, "captures")
    os.makedirs(CAPTURE_DIR, exist_ok=True)

    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.bus.subscribe("frame_ready", self.onFrame)
        self.bus.subscribe("enter_EducationMode", self.onEnter)
        self.bus.subscribe("button_press", self.captureFrame)
        self.bus.subscribe("camera_image_captured", self.onImageCaptured)
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
        self.marker_length = 0.02
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        model_PAPER = os.path.join(project_root, "core", "modes", "paperDetectAI.pt")
        
        self.paperModel = YOLO(model_PAPER)
        
        # --- Adjustable Padding Parameters ---
        self.padding_factor = 0.05  # Adjust this value (0.0 = no padding, 0.2 = 20% padding, etc.)
        self.min_padding_pixels = 20  # Minimum padding in pixels regardless of image size
        
        self.x1 = self.y1 = self.x2 = self.y2 = None

    def save_frame(self, frame):
        # 1. Find all existing images
        pattern = os.path.join(self.CAPTURE_DIR, "img_*.png")
        existing_files = glob.glob(pattern)

        # 2. Determine next index
        if existing_files:
            indices = [
                int(os.path.basename(f)[4:-4])  # img_XXXX.png → XXXX
                for f in existing_files
            ]
            next_index = max(indices) + 1
        else:
            next_index = 0

        # 3. Build filename
        filename = f"img_{next_index:04d}.png"
        save_path = os.path.join(self.CAPTURE_DIR, filename)

        # 4. Save file
        cv2.imwrite(save_path, frame)
        print("Saved:", save_path)

        return save_path

    async def onImageCaptured(self, data):
        """Detect paper, set autofocus, and trigger a second capture for clarity."""
        raw_frame = data.get("raw")
        filtered_frame = data.get("filtered")
        resolution = data.get("resolution", (0, 0))
        print(f"[EducationMode] 📸 Frame captured at {resolution}")

        if raw_frame is None or filtered_frame is None:
            print("[EducationMode] ❌ Missing frame data from capture.")
            print("[EducationMode] ℹ️ Tip: Align the camera directly above the paper for best accuracy.")
            return

        refocused = data.get("refocused", False)

        if refocused:
            print("[EducationMode] ✅ Refocused frame received. Proceeding with crop and analysis.")
            if None in [self.x1, self.y1, self.x2, self.y2]:
                print("[EducationMode] ⚠️ Missing paper coordinates; skipping crop.")
                return

            # Apply padding to create the final crop
            padded_coords = self.apply_padding(self.x1, self.y1, self.x2, self.y2, filtered_frame.shape)
            x1_pad, y1_pad, x2_pad, y2_pad = padded_coords
            
            frame_h, frame_w = filtered_frame.shape[:2]
            x1 = int(max(0, min(x1_pad, frame_w - 1)))
            y1 = int(max(0, min(y1_pad, frame_h - 1)))
            x2 = int(max(0, min(x2_pad, frame_w)))
            y2 = int(max(0, min(y2_pad, frame_h)))

            if x2 <= x1 or y2 <= y1:
                print("[EducationMode] ⚠️ Cropping bounds invalid after refocus.")
                return

            cropped = filtered_frame[y1:y2, x1:x2]
            if cropped.size == 0:
                print("[EducationMode] ⚠️ Cropped image is empty after refocus.")
                return

            # Save the cropped image for testing
            self.save_frame(cropped)
            print(f"[EducationMode] ✂️ Cropped size with padding: {cropped.shape}")
            print(f"[EducationMode] 📏 Applied padding factor: {self.padding_factor}")
            
            # Here you can add your new braille detection logic later
            print("[EducationMode] 🎯 Ready for new braille detection implementation")
            
            return

        # Reset detection state for initial autofocus pass
        self.x1 = self.y1 = self.x2 = self.y2 = None

        # Step 1: Detect paper boundaries
        paper_results = self.paperModel(raw_frame)
        for r in paper_results:
            for box in r.boxes.xyxy:
                self.x1, self.y1, self.x2, self.y2 = [int(coord) for coord in box]
                break
            break

        if None in [self.x1, self.y1, self.x2, self.y2]:
            print("[EducationMode] ❌ No paper detected. Please adjust camera alignment.")
            print("[EducationMode] ℹ️ Tip: Align the camera directly above the paper for best accuracy.")
            return

        frame_h, frame_w = raw_frame.shape[:2]

        # Apply padding for autofocus region
        padded_coords = self.apply_padding(self.x1, self.y1, self.x2, self.y2, raw_frame.shape)
        x1_pad, y1_pad, x2_pad, y2_pad = padded_coords

        # Clamp bounds to frame size
        self.x1 = max(0, min(x1_pad, frame_w - 1))
        self.y1 = max(0, min(y1_pad, frame_h - 1))
        self.x2 = max(0, min(x2_pad, frame_w))
        self.y2 = max(0, min(y2_pad, frame_h))

        if self.x2 <= self.x1 or self.y2 <= self.y1:
            print("[EducationMode] ❌ Invalid paper bounds detected.")
            print("[EducationMode] ℹ️ Tip: Align the camera directly above the paper for best accuracy.")
            return

        print(f"[EducationMode] 📄 Paper detected: ({self.x1}, {self.y1}) → ({self.x2}, {self.y2})")
        print(f"[EducationMode] 📏 Applied padding factor: {self.padding_factor}")

        # Step 2: Compute normalized bounding box for autofocus
        norm_x1 = self.x1 / frame_w
        norm_y1 = self.y1 / frame_h
        norm_x2 = self.x2 / frame_w
        norm_y2 = self.y2 / frame_h

        # Step 3: Publish focus region event
        await self.bus.publish("camera_set_focus_region", {
            "paper_borders": [float(norm_x1), float(norm_y1), float(norm_x2), float(norm_y2)]
        })
        print("[EducationMode] 🎯 Focus region published.")
        print("[EducationMode] ℹ️ Tip: Align the camera directly above the paper for best accuracy.")

        # Step 4: Wait for autofocus to stabilize, then re-capture
        await asyncio.sleep(1.0)
        print("[EducationMode] 🔁 Triggering second capture after AF lock...")
        await self.bus.publish("camera_capture", {"refocused": True, "wait_focus": True})

    def apply_padding(self, x1, y1, x2, y2, image_shape):
        """Apply adjustable padding to the detected paper coordinates"""
        frame_h, frame_w = image_shape[:2]
        
        # Calculate original dimensions
        width = x2 - x1
        height = y2 - y1
        
        # Calculate padding based on percentage of dimensions and minimum pixels
        pad_x = max(int(width * self.padding_factor), self.min_padding_pixels)
        pad_y = max(int(height * self.padding_factor), self.min_padding_pixels)
        
        # Apply padding
        x1_pad = x1 - pad_x
        y1_pad = y1 - pad_y
        x2_pad = x2 + pad_x
        y2_pad = y2 + pad_y
        
        # Clamp to image boundaries
        x1_pad = max(0, x1_pad)
        y1_pad = max(0, y1_pad)
        x2_pad = min(frame_w, x2_pad)
        y2_pad = min(frame_h, y2_pad)
        
        return x1_pad, y1_pad, x2_pad, y2_pad

    def set_padding_factor(self, factor):
        """Method to adjust padding factor dynamically"""
        self.padding_factor = max(0.0, min(factor, 0.3))  # Clamp between 0.0 and 0.5 (50%)
        print(f"[EducationMode] 🔧 Padding factor set to: {self.padding_factor}")

    # ... (keep existing methods unchanged below this point)
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
        if pin == 25:
            if self.captureFlag:
                return
            if not self.state.hasConnection:
                print("[EducationMode] You need an internet connection to scan the paper")
            if self.state.hasBraillePaper:
                print("There is already a paper")
                return
            if not self.hasVisibleMarker:
                print("Braille paper with the marker must be visible")
                pass

            self.captureFlag = True
            for i in range(1, 0, -1):
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
