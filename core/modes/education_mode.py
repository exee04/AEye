import cv2
from ultralytics import YOLO
import numpy as np
import asyncio
import os

class EducationMode:
    TARGET_IDS = {1, 5}

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
        model_BRAILLE = os.path.join(project_root, "core", "modes", "brailleDetectAI.pt")
        
        self.paperModel = YOLO(model_PAPER)
        self.brailleModel = YOLO(model_BRAILLE)
        
        # --- Sliding Window Parameters ---
        self.window_width = 640   # Adjust based on your model's optimal input size
        self.window_height = 640
        self.overlap = 0.3        # 30% overlap to avoid missing characters at edges
        self.step_x = int(self.window_width * (1 - self.overlap))
        self.step_y = int(self.window_height * (1 - self.overlap))
        
        self.x1 = self.y1 = self.x2 = self.y2 = None
        self.all_detections = []  # Store all detections across windows

    async def onImageCaptured(self, data):
        """Process captured image with sliding window approach"""
        self.x1 = self.y1 = self.x2 = self.y2 = None
        self.all_detections = []
        
        raw_frame = data.get("raw")
        filtered_frame = data.get("filtered")
        resolution = data.get("resolution", (0, 0))
        print(f"[EducationMode] Received captured frames at {resolution}")
        
        # Step 1: Detect paper boundaries
        paper_results = self.paperModel(raw_frame)
        for r in paper_results:
            for box in r.boxes.xyxy:
                self.x1, self.y1, self.x2, self.y2 = [int(coord) for coord in box]
                break  # Use first detection only
            break
        if None in [self.x1, self.y1, self.x2, self.y2]:
            print("[EducationMode] No paper detected!")
            return
        print(f"[EducationMode] Paper boundaries: ({self.x1}, {self.y1}) to ({self.x2}, {self.y2})")
        
        # Step 2: Crop the paper from filtered frame
        cropped = filtered_frame[int(self.y1):int(self.y2), int(self.x1):int(self.x2)]
        
        if cropped.size == 0:
            print("[EducationMode] Cropped image is empty!")
            return
            
        cv2.imwrite("core/modes/cropped_full.png", cropped)
        print(f"[EducationMode] Full cropped size: {cropped.shape}")
        
        # Step 3: Process with sliding window
        await self.process_with_sliding_window(cropped)
        
        # Step 4: Create final output with all detections
        await self.create_final_output(cropped)

    async def process_with_sliding_window(self, cropped_image):
        """Process cropped image using sliding window approach"""
        h, w = cropped_image.shape[:2]
        print(f"[SlidingWindow] Processing image of size {w}x{h} with window {self.window_width}x{self.window_height}")
        
        window_count = 0
        valid_windows = 0
        
        for y in range(0, h - self.window_height + 1, self.step_y):
            for x in range(0, w - self.window_width + 1, self.step_x):
                window_count += 1
                
                # Extract window
                window = cropped_image[y:y+self.window_height, x:x+self.window_width]
                
                # Skip windows that are too small
                if window.shape[0] < 50 or window.shape[1] < 50:
                    continue
                
                # Convert to RGB if needed
                if len(window.shape) == 2 or window.shape[2] == 1:
                    window_rgb = cv2.cvtColor(window, cv2.COLOR_GRAY2RGB)
                else:
                    window_rgb = window
                
                # Process window with Braille model
                try:
                    braille_results = self.brailleModel(window_rgb)
                    valid_windows += await self.process_window_detections(braille_results, x, y, window_rgb)
                    
                except Exception as e:
                    print(f"[SlidingWindow] Error processing window at ({x},{y}): {e}")
        
        print(f"[SlidingWindow] Processed {window_count} windows, {valid_windows} had valid detections")
        print(f"[SlidingWindow] Total detections: {len(self.all_detections)}")

    async def process_window_detections(self, results, offset_x, offset_y, window_img):
        """Process detections from a single window and store with global coordinates"""
        detection_count = 0
        
        for r in results:
            if len(r.boxes) == 0:
                continue
                
            for box in r.boxes:
                # Get local coordinates within window
                x1_local, y1_local, x2_local, y2_local = box.xyxy[0].cpu().numpy()
                conf = box.conf[0].cpu().numpy()
                cls = int(box.cls[0].cpu().numpy())
                
                # Convert to global coordinates in cropped image
                x1_global = int(offset_x + x1_local)
                y1_global = int(offset_y + y1_local)
                x2_global = int(offset_x + x2_local)
                y2_global = int(offset_y + y2_local)
                
                # Store detection with global coordinates and metadata
                detection = {
                    'coords': (x1_global, y1_global, x2_global, y2_global),
                    'confidence': float(conf),
                    'class': cls,
                    'class_name': self.brailleModel.names[cls] if hasattr(self.brailleModel, 'names') else str(cls)
                }
                
                # Check for duplicates (same area with high overlap)
                if not self.is_duplicate_detection(detection):
                    self.all_detections.append(detection)
                    detection_count += 1
        
        return detection_count

    def is_duplicate_detection(self, new_detection, overlap_threshold=0.7):
        """Check if detection overlaps significantly with existing detections"""
        x1_new, y1_new, x2_new, y2_new = new_detection['coords']
        area_new = (x2_new - x1_new) * (y2_new - y1_new)
        
        for existing in self.all_detections:
            x1_ex, y1_ex, x2_ex, y2_ex = existing['coords']
            area_ex = (x2_ex - x1_ex) * (y2_ex - y1_ex)
            
            # Calculate intersection
            x_left = max(x1_new, x1_ex)
            y_top = max(y1_new, y1_ex)
            x_right = min(x2_new, x2_ex)
            y_bottom = min(y2_new, y2_ex)
            
            if x_right > x_left and y_bottom > y_top:
                intersection_area = (x_right - x_left) * (y_bottom - y_top)
                overlap_ratio = intersection_area / min(area_new, area_ex)
                
                if overlap_ratio > overlap_threshold:
                    # Keep the detection with higher confidence
                    if new_detection['confidence'] > existing['confidence']:
                        self.all_detections.remove(existing)
                        return False
                    return True
        
        return False

    async def create_final_output(self, cropped_image):
        """Create final output image with all detections plotted"""
        # Convert to RGB for plotting if needed
        if len(cropped_image.shape) == 2 or cropped_image.shape[2] == 1:
            output_image = cv2.cvtColor(cropped_image, cv2.COLOR_GRAY2RGB)
        else:
            output_image = cropped_image.copy()
        
        # Plot all detections
        for i, detection in enumerate(self.all_detections):
            x1, y1, x2, y2 = detection['coords']
            conf = detection['confidence']
            cls_name = detection['class_name']
            
            # Draw bounding box
            cv2.rectangle(output_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw label
            label = f"{cls_name} {conf:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            cv2.rectangle(output_image, (x1, y1 - label_size[1] - 10), 
                         (x1 + label_size[0], y1), (0, 255, 0), -1)
            cv2.putText(output_image, label, (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        
        # Save final output
        cv2.imwrite("output.png", output_image)
        print(f"[EducationMode] Final output saved with {len(self.all_detections)} detections")
        
        # Optional: Save detection summary
        self.save_detection_summary()

    def save_detection_summary(self):
        """Save a summary of all detections"""
        summary = f"Braille Detection Summary\n"
        summary += f"Total detections: {len(self.all_detections)}\n"
        summary += f"Unique characters found: {len(set(d['class_name'] for d in self.all_detections))}\n"
        summary += "\nDetections:\n"
        
        for i, det in enumerate(self.all_detections):
            summary += f"{i+1:2d}. {det['class_name']:4s} - Confidence: {det['confidence']:.3f} - Position: {det['coords']}\n"
        
        with open("detection_summary.txt", "w") as f:
            f.write(summary)
        print("[EducationMode] Detection summary saved to detection_summary.txt")

    # ... (keep the rest of your existing methods unchanged: onFrame, captureFrame, onEnter, offlineCamera)
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
                pass

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
