import cv2
from ultralytics import YOLO
import numpy as np
import asyncio
import os
from collections import defaultdict

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
        
        # --- Enhanced Sliding Window Parameters ---
        self.window_sizes = [400, 550, 700]  # Multi-scale windows for different braille sizes
        self.overlap_factors = [0.6, 0.5, 0.4]  # Higher overlap for smaller windows
        self.confidence_threshold = 0.25  # Lower threshold to catch more detections
        self.iou_threshold = 0.3  # For duplicate detection
        
        self.x1 = self.y1 = self.x2 = self.y2 = None
        self.all_detections = []
        self.detection_stats = defaultdict(int)

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

            frame_h, frame_w = filtered_frame.shape[:2]
            x1 = int(max(0, min(self.x1, frame_w - 1)))
            y1 = int(max(0, min(self.y1, frame_h - 1)))
            x2 = int(max(0, min(self.x2, frame_w)))
            y2 = int(max(0, min(self.y2, frame_h)))

            if x2 <= x1 or y2 <= y1:
                print("[EducationMode] ⚠️ Cropping bounds invalid after refocus.")
                return

            cropped = filtered_frame[y1:y2, x1:x2]
            if cropped.size == 0:
                print("[EducationMode] ⚠️ Cropped image is empty after refocus.")
                return

            self.all_detections = []
            self.detection_stats.clear()
            cv2.imwrite("core/modes/cropped_full.png", cropped)
            print(f"[EducationMode] ✂️ Cropped size: {cropped.shape}")
            
            # Enhanced processing with multi-scale approach
            await self.enhanced_braille_detection(cropped)
            await self.create_final_output(cropped)
            return

        # Reset detection state for initial autofocus pass
        self.x1 = self.y1 = self.x2 = self.y2 = None
        self.all_detections = []
        self.detection_stats.clear()

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

        # Clamp bounds to frame size
        self.x1 = max(0, min(self.x1, frame_w - 1))
        self.y1 = max(0, min(self.y1, frame_h - 1))
        self.x2 = max(0, min(self.x2, frame_w))
        self.y2 = max(0, min(self.y2, frame_h))

        if self.x2 <= self.x1 or self.y2 <= self.y1:
            print("[EducationMode] ❌ Invalid paper bounds detected.")
            print("[EducationMode] ℹ️ Tip: Align the camera directly above the paper for best accuracy.")
            return

        print(f"[EducationMode] 📄 Paper detected: ({self.x1}, {self.y1}) → ({self.x2}, {self.y2})")

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

    async def enhanced_braille_detection(self, cropped_image):
        """Enhanced multi-scale braille detection with better coverage"""
        h, w = cropped_image.shape[:2]
        print(f"[EnhancedDetection] Processing image of size {w}x{h}")
        
        total_windows = 0
        total_detections = 0
        
        # Process at multiple scales
        for scale_idx, window_size in enumerate(self.window_sizes):
            if window_size > min(h, w):
                print(f"[EnhancedDetection] Skipping window size {window_size} (too large for image)")
                continue
                
            overlap = self.overlap_factors[scale_idx]
            step = int(window_size * (1 - overlap))
            
            print(f"[EnhancedDetection] Processing with window size {window_size}, step {step}, overlap {overlap*100}%")
            
            # Extend search beyond image boundaries to catch edge characters
            start_y = -step // 2
            end_y = h - window_size + step // 2
            start_x = -step // 2
            end_x = w - window_size + step // 2
            
            for y in range(start_y, end_y + 1, step):
                for x in range(start_x, end_x + 1, step):
                    total_windows += 1
                    
                    # Calculate actual window coordinates with boundary protection
                    x1_win = max(0, x)
                    y1_win = max(0, y)
                    x2_win = min(w, x + window_size)
                    y2_win = min(h, y + window_size)
                    
                    # Skip if window is too small
                    if (x2_win - x1_win) < 100 or (y2_win - y1_win) < 100:
                        continue
                    
                    window = cropped_image[y1_win:y2_win, x1_win:x2_win]
                    
                    # Process window
                    detections = await self.process_single_window(window, x1_win, y1_win, window_size)
                    total_detections += detections
        
        print(f"[EnhancedDetection] Completed: {total_windows} windows, {total_detections} raw detections")
        print(f"[EnhancedDetection] After deduplication: {len(self.all_detections)} unique detections")
        
        # Print detection statistics
        self.print_detection_statistics()

    async def process_single_window(self, window, offset_x, offset_y, window_size):
        """Process a single window and return number of valid detections"""
        detection_count = 0
        
        # Ensure window is in RGB format
        if len(window.shape) == 2 or window.shape[2] == 1:
            window_rgb = cv2.cvtColor(window, cv2.COLOR_GRAY2RGB)
        else:
            window_rgb = window
        
        try:
            # Run inference with adjusted confidence
            braille_results = self.brailleModel(window_rgb, conf=self.confidence_threshold)
            
            for r in braille_results:
                if len(r.boxes) == 0:
                    continue
                    
                for box in r.boxes:
                    conf = box.conf[0].cpu().numpy()
                    if conf < self.confidence_threshold:
                        continue
                        
                    # Convert local to global coordinates
                    x1_local, y1_local, x2_local, y2_local = box.xyxy[0].cpu().numpy()
                    x1_global = int(offset_x + x1_local)
                    y1_global = int(offset_y + y1_local)
                    x2_global = int(offset_x + x2_local)
                    y2_global = int(offset_y + y2_local)
                    
                    cls = int(box.cls[0].cpu().numpy())
                    class_name = self.brailleModel.names[cls] if hasattr(self.brailleModel, 'names') else str(cls)
                    
                    detection = {
                        'coords': (x1_global, y1_global, x2_global, y2_global),
                        'confidence': float(conf),
                        'class': cls,
                        'class_name': class_name,
                        'area': (x2_global - x1_global) * (y2_global - y1_global),
                        'window_size': window_size
                    }
                    
                    # Check for duplicates and add if unique
                    if not self.is_duplicate_detection(detection):
                        self.all_detections.append(detection)
                        self.detection_stats[class_name] += 1
                        detection_count += 1
                        
        except Exception as e:
            print(f"[WindowProcessing] Error at ({offset_x},{offset_y}): {e}")
        
        return detection_count

    def is_duplicate_detection(self, new_detection):
        """Improved duplicate detection using Intersection over Union (IoU)"""
        x1_new, y1_new, x2_new, y2_new = new_detection['coords']
        area_new = (x2_new - x1_new) * (y2_new - y1_new)
        
        for existing in self.all_detections:
            x1_ex, y1_ex, x2_ex, y2_ex = existing['coords']
            area_ex = (x2_ex - x1_ex) * (y2_ex - y1_ex)
            
            # Calculate intersection area
            x_left = max(x1_new, x1_ex)
            y_top = max(y1_new, y1_ex)
            x_right = min(x2_new, x2_ex)
            y_bottom = min(y2_new, y2_ex)
            
            if x_right > x_left and y_bottom > y_top:
                intersection_area = (x_right - x_left) * (y_bottom - y_top)
                union_area = area_new + area_ex - intersection_area
                
                if union_area > 0:
                    iou = intersection_area / union_area
                    
                    # If significant overlap, keep the higher confidence detection
                    if iou > self.iou_threshold:
                        if new_detection['confidence'] > existing['confidence']:
                            self.all_detections.remove(existing)
                            return False  # Not a duplicate, we're replacing
                        return True  # It's a duplicate, skip
        
        return False

    def print_detection_statistics(self):
        """Print detailed statistics about detected braille characters"""
        if not self.detection_stats:
            print("[Statistics] No braille characters detected")
            return
            
        total_chars = sum(self.detection_stats.values())
        unique_chars = len(self.detection_stats)
        
        print(f"\n[Statistics] 📊 Detection Summary:")
        print(f"[Statistics] Total characters: {total_chars}")
        print(f"[Statistics] Unique characters: {unique_chars}")
        print(f"[Statistics] Character breakdown:")
        
        for char, count in sorted(self.detection_stats.items()):
            percentage = (count / total_chars) * 100
            print(f"[Statistics]   {char}: {count} ({percentage:.1f}%)")

    async def create_final_output(self, cropped_image):
        """Create enhanced final output with detection visualization"""
        # Convert to RGB for plotting if needed
        if len(cropped_image.shape) == 2 or cropped_image.shape[2] == 1:
            output_image = cv2.cvtColor(cropped_image, cv2.COLOR_GRAY2RGB)
        else:
            output_image = cropped_image.copy()
        
        # Draw all detections with color coding by confidence
        for i, detection in enumerate(self.all_detections):
            x1, y1, x2, y2 = detection['coords']
            conf = detection['confidence']
            cls_name = detection['class_name']
            
            # Color code by confidence: green (high) -> yellow (medium) -> red (low)
            if conf > 0.7:
                color = (0, 255, 0)  # Green
            elif conf > 0.4:
                color = (0, 255, 255)  # Yellow
            else:
                color = (0, 0, 255)  # Red
            
            # Draw bounding box
            cv2.rectangle(output_image, (x1, y1), (x2, y2), color, 2)
            
            # Draw label with background
            label = f"{cls_name} {conf:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            
            # Label background
            cv2.rectangle(output_image, (x1, y1 - label_size[1] - 10), 
                         (x1 + label_size[0], y1), color, -1)
            
            # Label text
            cv2.putText(output_image, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        
        # Add statistics text to image
        stats_text = f"Detected: {len(self.all_detections)} braille characters"
        cv2.putText(output_image, stats_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Save final output
        cv2.imwrite("output.png", output_image)
        print(f"[EducationMode] ✅ Final output saved with {len(self.all_detections)} detections")
        
        # Save detailed detection summary
        self.save_detection_summary()

    def save_detection_summary(self):
        """Save comprehensive detection summary"""
        summary = "Braille Detection Summary - Enhanced Multi-Scale Approach\n"
        summary += "=" * 60 + "\n"
        summary += f"Total detections: {len(self.all_detections)}\n"
        summary += f"Unique characters: {len(set(d['class_name'] for d in self.all_detections))}\n"
        summary += f"Confidence threshold: {self.confidence_threshold}\n"
        summary += f"Window sizes used: {self.window_sizes}\n"
        summary += "\nCharacter Distribution:\n"
        
        # Sort by count descending
        char_counts = defaultdict(int)
        for det in self.all_detections:
            char_counts[det['class_name']] += 1
            
        for char, count in sorted(char_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(self.all_detections)) * 100
            summary += f"  {char}: {count:2d} ({percentage:5.1f}%)\n"
        
        summary += "\nDetailed Detections:\n"
        for i, det in enumerate(self.all_detections):
            summary += f"{i+1:3d}. {det['class_name']:4s} - Conf: {det['confidence']:.3f} - Pos: {det['coords']}\n"
        
        with open("detection_summary.txt", "w") as f:
            f.write(summary)
        print("[EducationMode] 📄 Detection summary saved to detection_summary.txt")

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
