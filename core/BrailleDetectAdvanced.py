# core/BrailleDetectAdvanced.py - Enhanced integration with C++ Braille Detector
import os
import json
import time
import cv2
import numpy as np

# Dynamic path resolution for security
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Try to import the C++ module with secure path resolution
try:
    BRAILLE_MODULE_DIR = os.path.join(CURRENT_DIR, "..", "braille_detector", "build")
    if os.path.exists(BRAILLE_MODULE_DIR):
        import sys
        sys.path.append(BRAILLE_MODULE_DIR)
    
    import braille_detector_native as bd
    CPP_DETECTOR_AVAILABLE = True
    print("[BrailleDetectAdvanced] C++ detector module loaded successfully")
except ImportError as e:
    CPP_DETECTOR_AVAILABLE = False
    print(f"[BrailleDetectAdvanced] C++ detector not available: {e}")
    print("[BrailleDetectAdvanced] Falling back to existing Python implementation")

class BrailleDetectAdvanced:
    """Enhanced Braille Detection service with C++ acceleration"""
    
    def __init__(self, bus):
        self.bus = bus
        self.isDetecting = False
        self.current_mode = "idle"
        self.education_submode = "idle"
        self.detected_letter = None
        self.touch_start_time = None
        self.touch_threshold = 1.0
        self.last_touch_position = None
        
        # Try to use C++ detector
        if CPP_DETECTOR_AVAILABLE:
            self.initialize_cpp_detector()
            self.detection_method = "cpp"
        else:
            self.initialize_python_detector()
            self.detection_method = "python"
        
        # Subscribe to events
        self.setup_event_subscriptions()
        
        print(f"[BrailleDetectAdvanced] Initialized with {self.detection_method} detection method")
    
    def initialize_cpp_detector(self):
        """Initialize the C++ Braille detector"""
        try:
            self.cpp_detector = bd.BrailleDetector()
            
            # Try to load configuration
            config_file = os.path.join("config", "braille_config.json")
            if os.path.exists(config_file):
                self.cpp_detector.load_config(config_file)
                print(f"[BrailleDetectAdvanced] Loaded C++ config from {config_file}")
            else:
                self.create_default_cpp_config()
            
            self.last_cpp_result = None
            self.last_cpp_letter = ""
            self.last_cpp_time = 0
            
        except Exception as e:
            print(f"[BrailleDetectAdvanced] Failed to initialize C++ detector: {e}")
            raise e
    
    def create_default_cpp_config(self):
        """Create default configuration for C++ detector"""
        config_dir = "config"
        os.makedirs(config_dir, exist_ok=True)
        print(f"[BrailleDetectAdvanced] Created default C++ config directory")
    
    def initialize_python_detector(self):
        """Initialize Python-only detection (fallback)"""
        print("[BrailleDetectAdvanced] Using Python-only detection")
        
        # Load braille letter mapping (same as original)
        self.braille_letters = {
            "100000": "A", "110000": "B", "100100": "C", "100110": "D",
            "100010": "E", "110100": "F", "110110": "G", "110010": "H",
            "010100": "I", "010110": "J", "101000": "K", "111000": "L",
            "101100": "M", "101110": "N", "101010": "O", "111100": "P",
            "111110": "Q", "111010": "R", "011100": "S", "011110": "T",
            "101001": "U", "111001": "V", "010111": "W", "101101": "X",
            "101111": "Y", "101011": "Z"
        }
        
        # Initialize mock braille_cpp for compatibility
        class MockBrailleCpp:
            @staticmethod
            def detect_braille(frame):
                return []
            
            @staticmethod
            def detect_fingers(frame):
                return []
        
        global braille_cpp
        braille_cpp = MockBrailleCpp()
    
    def setup_event_subscriptions(self):
        """Setup EventBus subscriptions"""
        self.bus.subscribe("start_detect", self.enter)
        self.bus.subscribe("stop_detect", self.exit)
        self.bus.subscribe("frame_ready", self.enter)
        self.bus.subscribe("enter_education_mode", self.on_education_enter)
        self.bus.subscribe("exit_education_mode", self.on_education_exit)
        self.bus.subscribe("enter_education_learn_mode", self.on_learn_enter)
        self.bus.subscribe("enter_education_quiz_mode", self.on_quiz_enter)
        self.bus.subscribe("enter_education_idle_mode", self.on_idle_enter)
        
        # New advanced subscription events
        self.bus.subscribe("toggle_cpp_debug", self.toggle_cpp_debug)
        self.bus.subscribe("start_cpp_calibration", self.start_cpp_calibration)
        self.bus.subscribe("switch_detection_method", self.switch_detection_method)
    
    # Event handlers (same as original for compatibility)
    async def enter(self, data):
        print("[BrailleDetectAdvanced] ENTER")
        self.isDetecting = True
        await self.bus.publish("tts", {"text": "Advanced Braille Mode activated"})
    
    async def exit(self, data):
        print("[BrailleDetectAdvanced] EXIT")
        self.isDetecting = False
    
    async def on_education_enter(self, data):
        self.current_mode = "education"
        print("[BrailleDetectAdvanced] Education mode entered")
    
    async def on_education_exit(self, data):
        self.current_mode = "idle"
        self.education_submode = "idle"
        self.isDetecting = False
        print("[BrailleDetectAdvanced] Education mode exited")
    
    async def on_learn_enter(self, data):
        self.education_submode = "learn"
        self.isDetecting = True
        print("[BrailleDetectAdvanced] Learn mode entered - detection enabled")
        await self.bus.publish("tts", {"text": "Learn mode activated with advanced detection."})
    
    async def on_quiz_enter(self, data):
        self.education_submode = "quiz"
        self.isDetecting = True
        print("[BrailleDetectAdvanced] Quiz mode entered - detection enabled")
        await self.bus.publish("tts", {"text": "Quiz mode activated with advanced detection."})
    
    async def on_idle_enter(self, data):
        self.education_submode = "idle"
        self.isDetecting = False
        print("[BrailleDetectAdvanced] Education idle mode - detection disabled")
    
    # New advanced methods
    async def toggle_cpp_debug(self, data):
        """Toggle C++ detector debug mode"""
        if self.detection_method == "cpp":
            try:
                enabled = data.get("enabled", True)
                self.cpp_detector.toggle_debug(enabled)
                await self.bus.publish("tts", {
                    "text": f"C++ debug mode {'enabled' if enabled else 'disabled'}"
                })
            except Exception as e:
                print(f"[BrailleDetectAdvanced] Failed to toggle debug mode: {e}")
    
    async def start_cpp_calibration(self, data):
        """Start C++ detector calibration"""
        if self.detection_method == "cpp":
            try:
                self.cpp_detector.start_calibration()
                await self.bus.publish("tts", {
                    "text": "Calibration started. Place the ArUco marker on a reference braille cell."
                })
            except Exception as e:
                print(f"[BrailleDetectAdvanced] Failed to start calibration: {e}")
    
    async def switch_detection_method(self, data):
        """Switch between C++ and Python detection methods"""
        new_method = data.get("method", "cpp")
        
        if new_method == "cpp" and CPP_DETECTOR_AVAILABLE:
            try:
                self.initialize_cpp_detector()
                self.detection_method = "cpp"
                await self.bus.publish("tts", {"text": "Switched to C++ detection method"})
            except Exception as e:
                print(f"[BrailleDetectAdvanced] Failed to switch to C++: {e}")
                return
        else:
            self.initialize_python_detector()
            self.detection_method = "python"
            await self.bus.publish("tts", {"text": "Switched to Python detection method"})
    
    async def on_frame(self, data):
        """Enhanced frame processing with C++ acceleration"""
        if not self.isDetecting or self.education_submode == "idle":
            return
            
        frame = data.get("frame")
        if frame is None:
            return
        
        try:
            if self.detection_method == "cpp":
                await self.process_frame_cpp(frame, data)
            else:
                await self.process_frame_python(frame, data)
                
        except Exception as e:
            print(f"[BrailleDetectAdvanced] Error processing frame: {e}")
    
    async def process_frame_cpp(self, frame, data):
        """Process frame using C++ detector"""
        vis_frame = frame.copy()
        
        # Convert to numpy array if needed
        if isinstance(frame, np.ndarray):
            frame_array = frame
        else:
            frame_array = np.array(frame, dtype=np.uint8)
        
        # Process through C++ detector
        result = self.cpp_detector.process_frame(
            frame_id=data.get("frame_id", 0),
            timestamp=data.get("timestamp", 0.0),
            frame_array=frame_array
        )
        
        if result.status == "ok":
            # Valid detection
            letter = result.letter.lower()  # Convert to lowercase
            
            # Check for touch/selection logic (same as original)
            current_touch = {
                "letter": letter,
                "confidence": result.confidence,
                "bbox": result.bbox
            }
            
            await self.handle_letter_touch(current_touch, result, vis_frame)
            
            # Publish enhanced detection event
            await self.bus.publish("braille_detected", {
                "letter": letter,
                "confidence": result.confidence,
                "bbox": result.bbox,
                "dot_mask": result.dot_mask,
                "method": "cpp",
                "timestamp": data.get("timestamp", 0.0)
            })
        
        elif result.status == "calibrating":
            # Calibration in progress
            cv2.putText(vis_frame, "CALIBRATING...", (10, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        else:
            # No detection or error
            cv2.putText(vis_frame, f"Status: {result.status}", (10, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Update frame with visualization
        data["frame"] = vis_frame
    
    async def process_frame_python(self, frame, data):
        """Process frame using Python-only detection (fallback)"""
        # Use the existing Python implementation
        vis_frame = frame.copy()
        
        # This mimics the original implementation
        # Add mock braille detection for demonstration
        cv2.putText(vis_frame, "Python Mode (Fallback)", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Mock detection logic
        mock_letters = ['a', 'b', 'c', 'd', 'e']
        mock_letter = mock_letters[data.get("frame_id", 0) % len(mock_letters)]
        
        cv2.putText(vis_frame, f"Mock Letter: {mock_letter.upper()}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
        data["frame"] = vis_frame
    
    async def handle_letter_touch(self, current_touch, result, vis_frame):
        """Handle letter touch detection logic"""
        if (self.last_touch_position is None or 
            self.last_touch_position != current_touch["letter"]):
            
            # New touch started
            self.touch_start_time = time.time()
            self.last_touch_position = current_touch["letter"]
            print(f"[BrailleDetectAdvanced] Touch started on letter: {current_touch['letter']}")
        else:
            # Same letter still being touched
            if time.time() - self.touch_start_time >= self.touch_threshold:
                # Letter selected!
                await self.on_letter_selected(current_touch["letter"], current_touch["confidence"])
                self.touch_start_time = None
                self.last_touch_position = None
        
        # Draw touch visualization
        bbox = current_touch["bbox"]
        cv2.rectangle(vis_frame, (bbox[0], bbox[1]), (bbox[0] + bbox[2], bbox[1] + bbox[3]), 
                     (0, 255, 0), 3)
        cv2.putText(vis_frame, f"CPP: {current_touch['letter'].upper()}", 
                   (bbox[0], bbox[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    async def on_letter_selected(self, letter, confidence):
        """Handle letter selection"""
        self.detected_letter = letter
        print(f"[BrailleDetectAdvanced] Letter selected: {letter} (confidence: {confidence:.2f})")
        
        if self.education_submode == "learn":
            await self.bus.publish("tts", {"text": f"The letter is {letter.upper()}"})
        elif self.education_submode == "quiz":
            await self.bus.publish("tts", {"text": f"What letter is this? You selected {letter.upper()}"})
        
        # Publish letter selection event
        await self.bus.publish("letter_selected", {
            "letter": letter,
            "confidence": confidence,
            "mode": self.education_submode,
            "method": self.detection_method
        })

# Export the class for use in main application
__all__ = ['BrailleDetectAdvanced']
