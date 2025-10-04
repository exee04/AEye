# core/BrailleDetect.py
import sys
import os
import json
import time
import cv2
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CPP_BUILD_DIR = os.path.join(BASE_DIR, "core", "BrailleCPPModules", "build")
sys.path.append(CPP_BUILD_DIR)

class BrailleDetect:
    def __init__(self, bus):
        self.bus = bus
        self.isDetecting = False
        self.current_mode = "idle"
        self.education_submode = "idle"
        self.detected_letter = None
        self.touch_start_time = None
        self.touch_threshold = 1.0  # seconds to hold for selection
        self.last_touch_position = None
        
        # Load braille letter mapping
        self.braille_letters = self.load_braille_letters()
        # Subscribe to events
        bus.subscribe("start_detect", self.enter)
        bus.subscribe("stop_detect", self.exit)
        self.bus.subscribe("frame_ready", self.on_frame)
        self.bus.subscribe("enter_education_mode", self.on_education_enter)
        self.bus.subscribe("exit_education_mode", self.on_education_exit)
        self.bus.subscribe("enter_education_learn_mode", self.on_learn_enter)
        self.bus.subscribe("enter_education_quiz_mode", self.on_quiz_enter)
        self.bus.subscribe("enter_education_idle_mode", self.on_idle_enter)
    def load_braille_letters(self):
        """Load braille letter mapping from JSON file"""
        try:
            with open("/home/ky/Desktop/AEye/core/BrailleLetters.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print("[BrailleDetect] BrailleLetters.json not found, using default mapping")
            return {
                "100000": "A", "110000": "B", "100100": "C", "100110": "D",
                "100010": "E", "110100": "F", "110110": "G", "110010": "H",
                "010100": "I", "010110": "J", "101000": "K", "111000": "L",
                "101100": "M", "101110": "N", "101010": "O", "111100": "P",
                "111110": "Q", "111010": "R", "011100": "S", "011110": "T",
                "101001": "U", "111001": "V", "010111": "W", "101101": "X",
                "101111": "Y", "101011": "Z"
            }

    async def enter(self, data):
        print("[BrailleDetect] ENTER")
        self.isDetecting = True
        await self.bus.publish("tts", {"text": "Volume Mode activated"})

    async def exit(self, data):
        print("[BrailleDetect] EXIT")
        self.isDetecting = False

    async def on_education_enter(self, data):
        self.current_mode = "education"
        print("[BrailleDetect] Education mode entered")

    async def on_education_exit(self, data):
        self.current_mode = "idle"
        self.education_submode = "idle"
        self.isDetecting = False
        print("[BrailleDetect] Education mode exited")

    async def on_learn_enter(self, data):
        self.education_submode = "learn"
        self.isDetecting = True
        print("[BrailleDetect] Learn mode entered - detection enabled")
        await self.bus.publish("tts", {"text": "Learn mode activated. Touch a braille letter to hear it."})

    async def on_quiz_enter(self, data):
        self.education_submode = "quiz"
        self.isDetecting = True
        print("[BrailleDetect] Quiz mode entered - detection enabled")
        await self.bus.publish("tts", {"text": "Quiz mode activated. Touch a braille letter to answer."})

    async def on_idle_enter(self, data):
        self.education_submode = "idle"
        self.isDetecting = False
        print("[BrailleDetect] Education idle mode - detection disabled")

    async def on_frame(self, data):
        if not self.isDetecting or self.education_submode == "idle":
            return
        frame = data.get("frame")
        if frame is None: 
            return

        # Create a copy for visualization
        vis_frame = frame.copy()

        # --- Stage 1 Braille Detection ---
        clusters = braille_cpp.detect_braille(frame)
        detected_letters = []
        
        for cluster in clusters:
            # Convert dot array to string for mapping
            dot_string = ''.join(map(str, cluster.dot_array))
            letter = self.braille_letters.get(dot_string, "?")
            
            # Store detected letter
            detected_letters.append({
                "letter": letter,
                "dots": cluster.dot_array,
                "dot_string": dot_string,
                "bbox": [cluster.bbox.x, cluster.bbox.y, cluster.bbox.width, cluster.bbox.height]
            })
            
            # Draw braille cluster visualization
            x, y, w, h = cluster.bbox.x, cluster.bbox.y, cluster.bbox.width, cluster.bbox.height
            cv2.rectangle(vis_frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
            cv2.putText(vis_frame, f"Braille: {letter}", (x, max(10, y - 8)), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            # Draw individual dots
            for i, dot in enumerate(cluster.dot_array):
                if dot == 1:
                    dot_x = x + (i % 2) * (w // 2) + w // 4
                    dot_y = y + (i // 2) * (h // 3) + h // 6
                    cv2.circle(vis_frame, (dot_x, dot_y), 3, (0, 180, 0), -1)

        # --- Finger Tracking ---
        fingers = braille_cpp.detect_fingers(frame)
        current_touch = None
        
        for f in fingers:
            # Draw finger marker
            cv2.circle(vis_frame, (int(f.center.x), int(f.center.y)), 8, (255, 0, 0), -1)
            cv2.putText(vis_frame, f"Finger {f.id}", (int(f.center.x) + 10, int(f.center.y)), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            
            # Check for collision with braille clusters
            for letter_data in detected_letters:
                x, y, w, h = letter_data["bbox"]
                if (x <= f.center.x <= x + w and y <= f.center.y <= y + h):
                    current_touch = letter_data
                    # Highlight touched letter
                    cv2.rectangle(vis_frame, (x, y), (x + w, y + h), (0, 0, 255), 3)
                    cv2.putText(vis_frame, f"TOUCHING: {letter_data['letter']}", (x, y - 20), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    break

        # --- Touch Detection Logic ---
        if current_touch:
            if self.last_touch_position is None or self.last_touch_position != current_touch["letter"]:
                # New touch started
                self.touch_start_time = time.time()
                self.last_touch_position = current_touch["letter"]
                print(f"[BrailleDetect] Touch started on letter: {current_touch['letter']}")
            else:
                # Same letter still being touched
                if time.time() - self.touch_start_time >= self.touch_threshold:
                    # Letter selected!
                    await self.on_letter_selected(current_touch["letter"])
                    self.touch_start_time = None
                    self.last_touch_position = None
        else:
            # No touch detected
            if self.touch_start_time is not None:
                print(f"[BrailleDetect] Touch released before threshold")
                self.touch_start_time = None
                self.last_touch_position = None

        # Add status text to visualization
        status_text = f"Mode: {self.education_submode} | Detected: {len(detected_letters)} letters"
        cv2.putText(vis_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        if current_touch and self.touch_start_time:
            progress = min(1.0, (time.time() - self.touch_start_time) / self.touch_threshold)
            progress_text = f"Touch Progress: {progress:.1%}"
            cv2.putText(vis_frame, progress_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Publish events
        await self.bus.publish("braille_detected", {"letters": detected_letters})
        await self.bus.publish("finger_detected", {"fingers": fingers})
        
        # Update the original frame with visualization
        data["frame"] = vis_frame

    async def on_letter_selected(self, letter):
        """Handle when a letter is selected by touch"""
        self.detected_letter = letter
        print(f"[BrailleDetect] Letter selected: {letter}")
        
        if self.education_submode == "learn":
            await self.bus.publish("tts", {"text": f"The letter is {letter}"})
        elif self.education_submode == "quiz":
            await self.bus.publish("tts", {"text": f"What letter is this? You selected {letter}"})
        
        # Publish letter selection event
        await self.bus.publish("letter_selected", {"letter": letter, "mode": self.education_submode})
