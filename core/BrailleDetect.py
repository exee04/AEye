# core/BrailleDetect.py
import sys
import json
import cv2
import time
sys.path.append("/home/ky/Desktop/AEye/core/BrailleCPPModules/build")
import braille_cpp

class BrailleDetect:
    def __init__(self, bus):
        self.bus = bus
        self.isDetecting = False
        self.detected_letter = None
        self.touch_start_time = None
        self.touch_threshold = 1.0  # seconds to hold touch
        self.last_touch_letter = None
        
        # Load braille letter mapping
        self.braille_letters = self.load_braille_letters()
        
        bus.subscribe("start_detect", self.enter)
        bus.subscribe("stop_detect", self.exit)
        self.bus.subscribe("frame_ready", self.on_frame)
        self.bus.subscribe("education_mode_entered", self.on_education_mode)
        self.bus.subscribe("education_mode_exited", self.on_education_mode_exit)
        
    def load_braille_letters(self):
        """Load braille letter mapping from JSON file"""
        try:
            with open("/home/ky/Desktop/AEye/core/BrailleLetters.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print("[BrailleDetect] BrailleLetters.json not found, using empty mapping")
            return {}
        except json.JSONDecodeError as e:
            print(f"[BrailleDetect] Error parsing BrailleLetters.json: {e}")
            return {}

    async def enter(self, data):
        print("[BrailleDetect] ENTER")
        self.isDetecting = True
        await self.bus.publish("tts", {"text": "Volume Mode activated"})

    async def exit(self, data):
        print("[BrailleDetect] EXIT")
        self.isDetecting = False
        
    async def on_education_mode(self, data):
        """Called when entering education mode"""
        print("[BrailleDetect] Education mode entered - braille detection enabled")
        self.isDetecting = True
        
    async def on_education_mode_exit(self, data):
        """Called when exiting education mode"""
        print("[BrailleDetect] Education mode exited - braille detection disabled")
        self.isDetecting = False

    async def on_frame(self, data):
        if not self.isDetecting:
            return
        frame = data.get("frame")
        if frame is None: 
            return

        # --- Stage 1 Braille Detection ---
        clusters = braille_cpp.detect_braille(frame)
        fingers = braille_cpp.detect_fingers(frame)
        
        # Process detected braille clusters
        for cluster in clusters:
            # Convert dot array to string for mapping
            dot_pattern = ''.join(map(str, cluster.dot_array))
            
            # Map braille pattern to letter
            letter = self.braille_letters.get(dot_pattern, "?")
            
            # Draw braille cluster visualization
            self.draw_braille_cluster(frame, cluster, letter)
            
            await self.bus.publish("braille_detected", {
                "letter": letter,
                "dots": cluster.dot_array,
                "dot_pattern": dot_pattern,
                "bbox": [cluster.bbox.x, cluster.bbox.y,
                         cluster.bbox.width, cluster.bbox.height]
            })

        # Process finger tracking
        for f in fingers:
            # Draw finger marker
            self.draw_finger_marker(frame, f)
            
            await self.bus.publish("finger_detected", {
                "id": f.id,
                "center": (f.center.x, f.center.y)
            })

        # --- Touch Detection and Letter Selection ---
        current_time = time.time()
        touch_detected = False
        
        for cluster in clusters:
            for f in fingers:
                if self.is_touching_braille(cluster, f):
                    touch_detected = True
                    dot_pattern = ''.join(map(str, cluster.dot_array))
                    letter = self.braille_letters.get(dot_pattern, "?")
                    
                    if self.touch_start_time is None:
                        # Start touch timer
                        self.touch_start_time = current_time
                        self.last_touch_letter = letter
                        print(f"[BrailleDetect] Touch started on letter: {letter}")
                    elif (current_time - self.touch_start_time >= self.touch_threshold and 
                          self.last_touch_letter == letter):
                        # Touch held long enough - select letter
                        await self.select_letter(letter, dot_pattern)
                        self.touch_start_time = None
                        self.last_touch_letter = None
                    break
        
        if not touch_detected:
            # Reset touch timer if no touch detected
            self.touch_start_time = None
            self.last_touch_letter = None

    def is_touching_braille(self, cluster, finger):
        """Check if finger is touching a braille cluster"""
        return (cluster.bbox.x <= finger.center.x <= cluster.bbox.x + cluster.bbox.width and
                cluster.bbox.y <= finger.center.y <= cluster.bbox.y + cluster.bbox.height)
    
    def draw_braille_cluster(self, frame, cluster, letter):
        """Draw visual representation of braille cluster"""
        x, y, w, h = cluster.bbox.x, cluster.bbox.y, cluster.bbox.width, cluster.bbox.height
        
        # Draw bounding box
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        # Draw letter label
        cv2.putText(frame, letter, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # Draw individual dots
        dot_size = min(w, h) // 6
        for i, dot in enumerate(cluster.dot_array):
            if dot == 1:  # Only draw raised dots
                row = i // 2
                col = i % 2
                dot_x = x + (col * w // 2) + w // 4
                dot_y = y + (row * h // 3) + h // 6
                cv2.circle(frame, (dot_x, dot_y), dot_size, (255, 0, 0), -1)
    
    def draw_finger_marker(self, frame, finger):
        """Draw finger marker"""
        center = (int(finger.center.x), int(finger.center.y))
        cv2.circle(frame, center, 10, (0, 0, 255), -1)
        cv2.putText(frame, f"F{finger.id}", (center[0] + 15, center[1]), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    
    async def select_letter(self, letter, dot_pattern):
        """Handle letter selection based on current education mode"""
        self.detected_letter = letter
        print(f"[BrailleDetect] Letter selected: {letter} (pattern: {dot_pattern})")
        
        # Publish letter selection event
        await self.bus.publish("letter_selected", {
            "letter": letter,
            "dot_pattern": dot_pattern,
            "timestamp": time.time()
        })
        
        # Get current education submode from state (we'll need to access this)
        # For now, we'll publish a general event that the education modes can handle
        await self.bus.publish("braille_letter_detected", {
            "letter": letter,
            "dot_pattern": dot_pattern
        })