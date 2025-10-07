import sys
import os
import json
import time
import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CPP_BUILD_DIR = os.path.join(BASE_DIR, "core", "BrailleCPPModules", "build")
sys.path.append(CPP_BUILD_DIR)

try:
    import braille_cpp
    HAS_CPP = True
    print("[BrailleDetect] Using C++ Braille module")
except ImportError:
    HAS_CPP = False
    print("[BrailleDetect] C++ module not found — using OpenCV fallback")

class BrailleDetect:
    def __init__(self, bus, debug=False):
        self.bus = bus
        self.debug = debug  # 👈 toggle visualization window
        self.isDetecting = False
        self.current_mode = "idle"
        self.education_submode = "idle"
        self.detected_letter = None
        self.touch_start_time = None
        self.touch_threshold = 1.0
        self.last_touch_position = None

        self.braille_letters = self.load_braille_letters()

        bus.subscribe("start_detect", self.enter)
        bus.subscribe("stop_detect", self.exit)
        bus.subscribe("frame_ready", self.on_frame)
        bus.subscribe("enter_education_mode", self.on_education_enter)
        bus.subscribe("exit_education_mode", self.on_education_exit)
        bus.subscribe("enter_education_learn_mode", self.on_learn_enter)
        bus.subscribe("enter_education_quiz_mode", self.on_quiz_enter)
        bus.subscribe("enter_education_idle_mode", self.on_idle_enter)

    def load_braille_letters(self):
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
        await self.bus.publish("tts", {"text": "Braille detection activated"})

    async def exit(self, data):
        print("[BrailleDetect] EXIT")
        self.isDetecting = False
        if self.debug:
            cv2.destroyAllWindows()

    async def on_education_enter(self, data):
        self.current_mode = "education"
        print("[BrailleDetect] Education mode entered")

    async def on_education_exit(self, data):
        self.current_mode = "idle"
        self.education_submode = "idle"
        self.isDetecting = False
        if self.debug:
            cv2.destroyAllWindows()
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
        if self.debug:
            cv2.destroyAllWindows()
        print("[BrailleDetect] Education idle mode - detection disabled")

    async def on_frame(self, data):
        if not self.isDetecting or self.education_submode == "idle":
            return

        frame = data.get("frame")
        if frame is None:
            return

        vis_frame = frame.copy()

        if HAS_CPP:
            clusters = braille_cpp.detect_braille(frame)
            fingers = braille_cpp.detect_fingers(frame)
            detected_letters = self._process_cpp_results(vis_frame, clusters)
        else:
            detected_letters = self._detect_braille_opencv(vis_frame)
            fingers = self._detect_fingers_opencv(vis_frame)

        current_touch = None
        for f in fingers:
            fx, fy = f["center"]
            cv2.circle(vis_frame, (int(fx), int(fy)), 8, (255, 0, 0), -1)
            for letter_data in detected_letters:
                x, y, w, h = letter_data["bbox"]
                if (x <= fx <= x + w and y <= fy <= y + h):
                    current_touch = letter_data
                    cv2.rectangle(vis_frame, (x, y), (x + w, y + h), (0, 0, 255), 3)
                    cv2.putText(vis_frame, f"Touching: {letter_data['letter']}", (x, y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    break

        # Touch logic
        if current_touch:
            if self.last_touch_position != current_touch["letter"]:
                self.touch_start_time = time.time()
                self.last_touch_position = current_touch["letter"]
                print(f"[BrailleDetect] Touch started on letter: {current_touch['letter']}")
            elif time.time() - self.touch_start_time >= self.touch_threshold:
                await self.on_letter_selected(current_touch["letter"])
                self.last_touch_position = None
                self.touch_start_time = None
        else:
            self.last_touch_position = None
            self.touch_start_time = None

        # Display debug visualization 👇
        if self.debug:
            cv2.putText(vis_frame, f"Mode: {self.education_submode}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(vis_frame, f"Letters: {len(detected_letters)}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.imshow("Braille Debug", vis_frame)
            cv2.waitKey(1)  # allows window to update

        await self.bus.publish("braille_detected", {"letters": detected_letters})
        await self.bus.publish("finger_detected", {"fingers": fingers})
        data["frame"] = vis_frame

    # --------------------
    # FALLBACK DETECTORS
    # --------------------
    def _detect_braille_opencv(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 150, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detected = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if 5 < w < 50 and 5 < h < 50:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 1)
                dot_string = "100000"  # dummy example
                letter = self.braille_letters.get(dot_string, "?")
                detected.append({"letter": letter, "dot_string": dot_string, "bbox": [x, y, w, h]})
        return detected

    def _detect_fingers_opencv(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_skin = np.array([0, 30, 60], dtype=np.uint8)
        upper_skin = np.array([20, 150, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower_skin, upper_skin)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        fingers = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 1000:
                M = cv2.moments(cnt)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    fingers.append({"center": (cx, cy)})
        return fingers

    def _process_cpp_results(self, frame, clusters):
        detected = []
        for c in clusters:
            x, y, w, h = c.bbox.x, c.bbox.y, c.bbox.width, c.bbox.height
            dot_string = ''.join(map(str, c.dot_array))
            letter = self.braille_letters.get(dot_string, "?")
            detected.append({"letter": letter, "dot_string": dot_string, "bbox": [x, y, w, h]})
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
            cv2.putText(frame, letter, (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        return detected

    async def on_letter_selected(self, letter):
        print(f"[BrailleDetect] Letter selected: {letter}")
        self.detected_letter = letter
        if self.education_submode == "learn":
            await self.bus.publish("tts", {"text": f"The letter is {letter}"})
        elif self.education_submode == "quiz":
            await self.bus.publish("tts", {"text": f"You selected {letter}"})
        await self.bus.publish("letter_selected", {"letter": letter, "mode": self.education_submode})

