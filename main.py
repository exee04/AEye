import time
from gpiozero import Button, DigitalOutputDevice
import threading
import subprocess
from queue import Queue, Empty, Full
import sys
import sounddevice as sd
import numpy as np
from scipy.signal import resample_poly
from scipy.io.wavfile import write
from google.cloud import speech
import os
import difflib
from picamera2 import Picamera2
import cv2
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from SystemModules.Prompts.SystemPrompts import (
    MAIN_PROMPT_MAP,
    COMMON_PROMPT_MAP,
    EDUCATION_PROMPT_MAP,
    QUIZ_PROMPT_MAP
)
from collections import deque

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SystemState:
    active_learn_mode: bool = False
    active_quiz_mode: bool = False
    braille_positions: List[Dict] = field(default_factory=list)
    marker_corners: Optional[np.ndarray] = None
    last_transcript: str = ""
    last_prompt: str = ""
    base_marker_center: Optional[Tuple[int, int]] = None
    last_scan_time: float = 0.0

# Initialize state
state = SystemState()

# Initialize ArUco dictionary and detector
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
parameters = cv2.aruco.DetectorParameters()
aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

# Audio recording parameters
fs = 44100  # Original sample rate
target_fs = 16000  # Target sample rate for Google Speech-to-Text
filename = "output.wav"

# Initialize Google Speech-to-Text client
client = speech.SpeechClient()
config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=target_fs,
    language_code="en-US",
)

# Initialize vibration module
vibration_module = DigitalOutputDevice(16)

# Initialize camera
picam2 = None
camera_active = False
display_thread = None
processing_thread = None
WINDOW_NAME = "AEye Camera Feed"
window_created = False

# Add this near the top of the file with other global variables
current_touched_letter = None
last_interaction_point = None
last_interaction_time = 0
last_marker_center = None
last_marker_time = 0
LINGER_DURATION = 0.5  # How long to keep showing the last known position (in seconds)

# Add these global variables after other global variables
POSITION_HISTORY_SIZE = 3  # Number of frames to average for position smoothing
marker_center_history = deque(maxlen=POSITION_HISTORY_SIZE)
interaction_point_history = deque(maxlen=POSITION_HISTORY_SIZE)

def display_camera_feed():
    """Display camera feed with current mode text overlay"""
    global picam2, current_mode, camera_active, window_created
    if not camera_active or picam2 is None:
        return
        
    try:
        # Create named window if it doesn't exist
        if not window_created:
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW_NAME, 640, 480)  # Set initial window size to match camera resolution
            window_created = True
            print("Camera window created")
        
        print("Starting camera display loop...")
        while True:  # Keep running regardless of mode
            try:
                frame = picam2.capture_array()
                
                # Add mode text overlay
                cv2.putText(frame, f"Mode: {current_mode}", (20, 40), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 2)  # Adjusted text size for 720p
                
                # Display the frame
                cv2.imshow(WINDOW_NAME, frame)
                cv2.waitKey(1)  # Ensure window is updated
                
                # Break loop if 'q' is pressed
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            except Exception as e:
                print(f"Error in camera display loop: {e}")
                break
                
    except Exception as e:
        print(f"Error in display_camera_feed: {e}")
    finally:
        if window_created:
            cv2.destroyWindow(WINDOW_NAME)
            window_created = False
        print("Camera display loop ended")

def stop_camera():
    """Stop and cleanup camera resources"""
    global picam2, camera_active, display_thread, processing_thread, window_created
    try:
        # Signal the threads to stop
        camera_active = False
        
        # Wait for threads to finish if they exist
        if display_thread and display_thread.is_alive():
            display_thread.join(timeout=1.0)
        if processing_thread and processing_thread.is_alive():
            processing_thread.join(timeout=1.0)
        
        # Clean up camera resources
        if picam2 is not None:
            try:
                picam2.stop()
                picam2.close()
            except Exception as e:
                print(f"Error stopping picam2: {e}")
            finally:
                picam2 = None
        
        # Ensure window is closed if it exists
        if window_created:
            cv2.destroyWindow(WINDOW_NAME)
            window_created = False
        
    except Exception as e:
        print(f"Error in stop_camera: {e}")

def initialize_camera():
    """Initialize the camera with proper configuration"""
    global picam2, camera_active, display_thread, frame_queue, processing_thread
    try:
        # Ensure any existing camera is properly stopped
        stop_camera()
        
        print("Initializing camera...")
        # Initialize new camera
        picam2 = Picamera2()
        
        # Configure camera with specific settings
        config = picam2.create_preview_configuration(
            main={"format": "RGB888", "size": (640, 480)},
            buffer_count=4  # Increase buffer count for better performance
        )
        print("Camera configuration created")
        
        picam2.configure(config)
        print("Camera configured")
        
        picam2.start()
        print("Camera started")
        time.sleep(1)  # Camera warm-up
        
        # Create frame queue
        frame_queue = Queue(maxsize=2)
        print("Frame queue created")
        
        # Set camera as active and start both threads
        camera_active = True
        
        # Start display thread
        display_thread = threading.Thread(target=display_frames, args=(frame_queue,), daemon=True)
        display_thread.start()
        print("Display thread started")
        
        # Start processing thread
        processing_thread = threading.Thread(target=process_frames, args=(frame_queue,), daemon=True)
        processing_thread.start()
        print("Processing thread started")
        
        # Give the threads time to initialize
        time.sleep(0.5)
        
        return True
    except Exception as e:
        print(f"Failed to initialize camera: {e}")
        camera_active = False
        return False

# Initialize all buttons with hold_time for hold detection and bounce_time for debouncing
funcButton1 = Button(17, hold_time=1.0, bounce_time=0.1)  # 1 second hold time, 100ms bounce time
funcButton2 = Button(27, hold_time=1.0, bounce_time=0.1)
funcButton3 = Button(22, hold_time=1.0, bounce_time=0.1)
funcButton4 = Button(23, hold_time=1.0, bounce_time=0.1)
mainBtn = Button(24, hold_time=0.1, bounce_time=0.1)
volUpBtn = Button(6, hold_time=1.0, bounce_time=0.1)
volDownBtn = Button(5, hold_time=1.0, bounce_time=0.1)

# Global mode flags
current_mode = "main"  # Can be "main", "education", or "score"

# Volume and voice settings
current_volume = 100
voice_speed = 150
on_volume_control = False

def vibrate(duration=0.5):
    """Activate vibration module for specified duration"""
    vibration_module.on()
    time.sleep(duration)
    vibration_module.off()

def TTS(text):
    """Text-to-speech function with current volume and speed settings"""
    threading.Thread(target=lambda: subprocess.run([
        'espeak-ng', 
        "-a", str(current_volume),
        "-s", str(voice_speed),
        "-p", "70",
        text
    ])).start()

def update_volume(delta):
    """Update volume with bounds checking"""
    global current_volume
    new_volume = current_volume + delta
    if 0 <= new_volume <= 200:
        current_volume = new_volume
        return True
    return False

def update_voice_speed(delta):
    """Update voice speed with bounds checking"""
    global voice_speed
    new_speed = voice_speed + delta
    if 100 <= new_speed <= 280:
        voice_speed = new_speed
        return True
    return False

def wait_volbutton():
    """Wait for volume button press and return the button number"""
    queue = Queue()
    volUpBtn.when_pressed = queue.put
    volDownBtn.when_pressed = queue.put
    e = queue.get()
    return e.pin.number

def volumeControl():
    """Handle volume and voice speed control"""
    global on_volume_control
    print("Volume control active")
    while True:
        b = wait_volbutton()
        if on_volume_control:
            if b == 6:  # Volume up
                if update_volume(20):
                    TTS("Volume Up")
                    vibrate()
                else:
                    TTS("Max Volume")
                    vibrate()
            elif b == 5:  # Volume down
                if update_volume(-20):
                    TTS("Volume Down")
                    vibrate()
                else:
                    TTS("No Volume")
                    vibrate()
        else:
            if b == 6:  # Speed up
                if update_voice_speed(10):
                    TTS("Increasing Talking Speed")
                    vibrate()
                else:
                    TTS("Max Talking Speed")
                    vibrate()
            elif b == 5:  # Speed down
                if update_voice_speed(-10):
                    TTS("Decreasing Talking Speed")
                    vibrate()
                else:
                    TTS("Minimum Talking Speed")
                    vibrate()
        time.sleep(0.2)

def button_tapped(button_name):
    """Handle button tap with short vibration"""
    print(f"{button_name} tapped!")
    TTS(f"{button_name} tapped!")
    vibrate(0.2)

def display_frames(frame_queue):
    """Display frames in a separate thread"""
    global window_created, current_mode
    
    try:
        # Create window if it doesn't exist
        if not window_created:
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW_NAME, 1280, 720)
            window_created = True
            print("Display window created")
        
        last_frame_time = time.time()
        frame_count = 0
        target_fps = 8  # Target 8 FPS
        frame_interval = 1.0 / target_fps  # Time between frames
        
        while camera_active:  # Run as long as camera is active
            try:
                current_time = time.time()
                elapsed = current_time - last_frame_time
                
                # Get frame from queue with timeout
                try:
                    frame = frame_queue.get(timeout=0.1)
                    if frame is not None:
                        # Display mode text
                        mode_text = "Learning Mode" if state.active_learn_mode else "Quiz Mode" if state.active_quiz_mode else current_mode.capitalize()
                        cv2.putText(frame, f"Mode: {mode_text}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        
                        # Display frame
                        cv2.imshow(WINDOW_NAME, frame)
                        
                        # Handle key press
                        key = cv2.waitKey(1) & 0xFF
                        if key == ord('q'):
                            print("Quit key pressed")
                            break
                        
                        # Calculate and display FPS
                        frame_count += 1
                        if frame_count % 8 == 0:  # Update FPS display every 8 frames
                            fps = 8 / (current_time - last_frame_time)
                            print(f"Display FPS: {fps:.2f}")
                            last_frame_time = current_time
                            
                except Empty:
                    # No frame available, continue
                    time.sleep(0.01)
                    continue
                
                # Sleep to maintain target FPS
                sleep_time = frame_interval - (time.time() - current_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                print(f"Error in display loop: {e}")
                # Try to recreate window if display fails
                try:
                    cv2.destroyWindow(WINDOW_NAME)
                    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
                    cv2.resizeWindow(WINDOW_NAME, 1280, 720)
                except:
                    pass
                continue
            
    except Exception as e:
        print(f"Error in display thread: {e}")
    finally:
        if window_created:
            cv2.destroyWindow(WINDOW_NAME)
            window_created = False
        print("Display thread ended")

def draw_braille_positions(frame, marker_center, braille_positions, distance, rot_matrix, tvec, camera_matrix, dist_coeffs):
    global last_marker_center, last_marker_time
    
    # Update last known marker position
    if marker_center is not None:
        last_marker_center = marker_center
        last_marker_time = time.time()
    
    # If we have a last known position and it's within the linger duration, use it
    current_time = time.time()
    if last_marker_center is not None and (current_time - last_marker_time) < LINGER_DURATION:
        marker_center = last_marker_center
    elif (current_time - last_marker_time) >= LINGER_DURATION:
        last_marker_center = None
        return
    
    # Scale factor based on distance
    scale_factor = 1.0 / (distance + 0.1)
    base_size = 60
    scaled_w = int(base_size * scale_factor)
    scaled_h = int(base_size * scale_factor)
    
    # Ensure minimum size for visibility
    scaled_w = max(scaled_w, 30)
    scaled_h = max(scaled_h, 30)
    
    for braille in braille_positions:
        rel_x, rel_y = braille["relative"]
        label = braille["label"]
        
        # Convert relative position to 3D point (in marker's coordinate system)
        # Convert from mm to meters and invert Y coordinate
        point_3d = np.array([
            rel_x/1000.0,  # Convert mm to meters
            -rel_y/1000.0,  # Invert Y and convert to meters
            0
        ], dtype=np.float32)
        
        # Transform point using rotation matrix
        point_3d_rotated = np.dot(rot_matrix, point_3d)
        
        # Project the transformed point back to 2D
        point_2d, _ = cv2.projectPoints(
            point_3d_rotated.reshape(1, 1, 3),
            np.zeros(3, dtype=np.float32),
            tvec,
            camera_matrix,
            dist_coeffs
        )
        
        # Get the projected point
        abs_x = int(point_2d[0][0][0])
        abs_y = int(point_2d[0][0][1])
        
        # Calculate box corners with right side trimmed
        right_trim = int(scaled_w * 0.3)  # Trim 30% from the right side
        top_left = (int(abs_x - scaled_w/2), int(abs_y - scaled_h/2))
        bottom_right = (int(abs_x + scaled_w/2 - right_trim), int(abs_y + scaled_h/2))
        
        # Calculate alpha based on time since last detection
        alpha = 1.0 - ((current_time - last_marker_time) / LINGER_DURATION)
        alpha = max(0.3, min(1.0, alpha))  # Keep alpha between 0.3 and 1.0
        
        # Draw filled rectangle with semi-transparent green
        overlay = frame.copy()
        cv2.rectangle(overlay, top_left, bottom_right, (0, 255, 0), -1)  # -1 for filled rectangle
        cv2.addWeighted(overlay, 0.3 * alpha, frame, 1 - (0.3 * alpha), 0, frame)  # Blend with original frame
        
        # Draw border
        cv2.rectangle(frame, top_left, bottom_right, (0, 255, 0), 2)
        
        # Adjust text size based on box size
        text_scale = max(0.3, min(0.7, scale_factor))
        cv2.putText(frame, label, 
                   (top_left[0], top_left[1] - 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 
                   text_scale, 
                   (0, 255, 0), 
                   2)
        
        # Store the box coordinates in the braille object for interaction detection
        braille['box_coords'] = {
            'top_left': top_left,
            'bottom_right': bottom_right
        }

def smooth_position(position, history):
    """Smooth position using moving average"""
    if position is None:
        return None
        
    history.append(position)
    if len(history) < 2:
        return position
        
    # Calculate average position
    avg_x = sum(p[0] for p in history) / len(history)
    avg_y = sum(p[1] for p in history) / len(history)
    return (int(avg_x), int(avg_y))

def process_marker_detection(frame, camera_matrix, dist_coeffs, marker_size, axis_points):
    global marker_center_history, interaction_point_history
    
    # Convert to grayscale for ArUco detection
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    
    # Detect ArUco markers
    corners, ids, _ = aruco_detector.detectMarkers(gray)
    
    interaction_point = None
    current_marker_center = None
    marker_tvec = None
    marker_distance = None
    marker_rot_matrix = None
    
    if ids is not None:
        # Process marker ID 1 (for braille positions)
        if 1 in ids and current_mode == "education" and state.braille_positions:
            marker_index = np.where(ids == 1)[0][0]
            marker_corners = corners[marker_index][0]
            
            # Define the marker points in 3D space
            marker_points = np.array([
                [-marker_size/2, marker_size/2, 0],
                [marker_size/2, marker_size/2, 0],
                [marker_size/2, -marker_size/2, 0],
                [-marker_size/2, -marker_size/2, 0]
            ], dtype=np.float32)
            
            # Calculate pose
            ret, rvec, tvec = cv2.solvePnP(
                marker_points,
                marker_corners,
                camera_matrix,
                dist_coeffs
            )
            
            # Calculate distance
            distance = np.linalg.norm(tvec)
            
            # Get rotation matrix from rotation vector
            rot_matrix, _ = cv2.Rodrigues(rvec)
            
            # Store values for braille drawing
            marker_tvec = tvec
            marker_distance = distance
            marker_rot_matrix = rot_matrix
            
            # Draw axes and get center
            current_marker_center = draw_axes_and_info(frame, marker_corners, camera_matrix, dist_coeffs, 
                                                     marker_size, axis_points, 1)
            
            # Smooth marker center position
            current_marker_center = smooth_position(current_marker_center, marker_center_history)
            
            # Draw braille positions if we have them
            if state.braille_positions:
                draw_braille_positions(frame, current_marker_center, state.braille_positions, 
                                    distance, rot_matrix, tvec, camera_matrix, dist_coeffs)
        
        # Process marker ID 5 (for interaction pointer)
        if 5 in ids:
            marker_index = np.where(ids == 5)[0][0]
            marker_corners = corners[marker_index][0]
            interaction_point = draw_axes_and_info(frame, marker_corners, camera_matrix, dist_coeffs, 
                                                 marker_size, axis_points, 5)
            
            # Smooth interaction point position
            interaction_point = smooth_position(interaction_point, interaction_point_history)
    
    return current_marker_center, interaction_point

def check_finger_interaction(frame, interaction_point, braille_positions, current_marker_center):
    global current_touched_letter, last_interaction_point, last_interaction_time
    
    current_time = time.time()
    
    # Update last known interaction point
    if interaction_point is not None:
        last_interaction_point = interaction_point
        last_interaction_time = current_time
    
    # If we have a last known position and it's within the linger duration, use it
    if last_interaction_point is not None and (current_time - last_interaction_time) < LINGER_DURATION:
        interaction_point = last_interaction_point
    elif (current_time - last_interaction_time) >= LINGER_DURATION:
        last_interaction_point = None
        current_touched_letter = None
        return None
    
    if interaction_point is None or current_marker_center is None or current_mode != "education":
        current_touched_letter = None
        return None
        
    fx, fy = interaction_point
    current_letter = None
    
    # Calculate alpha based on time since last detection
    alpha = 1.0 - ((current_time - last_interaction_time) / LINGER_DURATION)
    alpha = max(0.3, min(1.0, alpha))  # Keep alpha between 0.3 and 1.0
    
    # Draw the interaction point with fading effect
    cv2.circle(frame, (fx, fy), 5, (0, int(255 * alpha), int(255 * alpha)), -1)  # Yellow dot for interaction point
    
    for braille in braille_positions:
        if 'box_coords' not in braille:
            continue
            
        top_left = braille['box_coords']['top_left']
        bottom_right = braille['box_coords']['bottom_right']
        
        # Check if interaction point is within the rectangle
        if (top_left[0] <= fx <= bottom_right[0] and 
            top_left[1] <= fy <= bottom_right[1]):
            
            currentBrailleLetter = braille['label']
            current_letter = currentBrailleLetter
            current_touched_letter = currentBrailleLetter
            
            # Add timestamp tracking for each braille position
            if not hasattr(braille, 'touch_start_time'):
                braille['touch_start_time'] = current_time
                braille['touch_duration'] = 0
            else:
                braille['touch_duration'] = current_time - braille['touch_start_time']
            
            # Display touch duration
            if braille['touch_duration'] > 0:
                cv2.putText(frame, f"Touch: {braille['touch_duration']:.1f}s", 
                          (top_left[0] - 40, top_left[1] - 30), 
                          cv2.FONT_HERSHEY_SIMPLEX, 
                          0.5, 
                          (0, 255, 0), 
                          2)
            
            # Only trigger if finger has been on the position for at least 1 second
            if braille['touch_duration'] >= 1.0:
                if state.active_learn_mode:
                    TTS(f"You are touching letter {currentBrailleLetter}")
                    vibrate()
                    time.sleep(1)
                    braille['touch_start_time'] = None
                    braille['touch_duration'] = 0
                    return currentBrailleLetter
                elif state.active_quiz_mode:
                    run_quiz_question(currentBrailleLetter)
                    vibrate()
                    braille['touch_start_time'] = None
                    braille['touch_duration'] = 0
                    return currentBrailleLetter
        else:
            if hasattr(braille, 'touch_start_time'):
                braille['touch_start_time'] = None
                braille['touch_duration'] = 0
    
    if not current_letter:
        current_touched_letter = None
    
    # Display current letter being pointed at (if any)
    if current_letter:
        cv2.putText(frame, f"Pointing at: {current_letter}", 
                   (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 
                   1, 
                   (0, 255, 0), 
                   2)
    else:
        cv2.putText(frame, "Pointing at: None", 
                   (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 
                   1, 
                   (0, 255, 0), 
                   2)
    
    return None

def educationMode():
    global current_mode, state
    current_mode = "education"
    print("Education Mode")
    TTS("Education Mode")
    vibrate(0.5)
    
    if not camera_active:
        if initialize_camera():
            TTS("Camera initialized for education mode")
        else:
            TTS("Failed to initialize camera")
            return
    
    # Load braille positions from JSON
    try:
        print("Attempting to load braille positions from JSON...")
        with open('braille_scan_20250520_231629.json', 'r') as f:
            braille_data = json.load(f)
            state.braille_positions = braille_data['braille_positions']
            print("✅ Loaded braille positions from JSON")
            print(f"Number of braille positions loaded: {len(state.braille_positions)}")
    except Exception as e:
        logger.error(f"Failed to load braille positions: {e}")
        TTS("Failed to load braille positions. Please check the JSON file.")
        return
    
    # Set up button actions for education mode
    setup_button_actions()
    
    try:
        # Keep the mode active until changed
        while current_mode == "education":
            # Check if processing thread is still alive
            if not processing_thread.is_alive():
                print("Processing thread has stopped")
                break
                
            # Small delay to prevent CPU overuse
            time.sleep(0.1)
            
            # Check for button presses
            if funcButton1.is_pressed:
                print("Button 1 pressed in education mode")
                time.sleep(0.2)  # Debounce
            elif funcButton2.is_pressed:
                print("Button 2 pressed in education mode")
                set_mode("score")
                return  # Exit immediately after mode change
            elif funcButton3.is_pressed:
                print("Button 3 pressed in education mode")
                checkFinger()
                time.sleep(0.2)  # Debounce
            elif funcButton4.is_pressed:
                print("Button 4 pressed in education mode")
                set_mode("secondary")
                return  # Exit immediately after mode change
            elif mainBtn.is_pressed:
                print("Main button pressed in education mode")
                speak()
                time.sleep(0.2)  # Debounce
        
        print("Exiting education mode")
        
    except Exception as e:
        logger.error(f"Error in education mode: {e}")
        print(f"Detailed error in education mode: {str(e)}")
        TTS("An error occurred in education mode")
    finally:
        # Clean up education mode specific states
        state.active_learn_mode = False
        state.active_quiz_mode = False
        if hasattr(state, 'braille_positions'):
            for braille in state.braille_positions:
                if hasattr(braille, 'touch_start_time'):
                    braille['touch_start_time'] = None
                    braille['touch_duration'] = 0
        return

def setup_button_actions():
    """Set up button actions based on current mode"""
    global current_mode
    
    # Clear all button actions first
    funcButton1.when_pressed = None
    funcButton2.when_pressed = None
    funcButton3.when_pressed = None
    funcButton4.when_pressed = None
    mainBtn.when_held = None
    
    # Set up common button actions
    volUpBtn.when_pressed = lambda: button_tapped("Volume Up")
    volDownBtn.when_pressed = lambda: button_tapped("Volume Down")
    
    # Set up mode-specific button actions
    if current_mode == "main":
        funcButton1.when_pressed = lambda: set_mode("education")
        funcButton2.when_pressed = lambda: set_mode("score")
        funcButton3.when_pressed = lambda: button_tapped("Button 3")
        funcButton4.when_pressed = lambda: set_mode("secondary")
    elif current_mode == "education":
        # In education mode, we'll handle button presses in the educationMode loop
        funcButton1.when_pressed = lambda: print("Button 1 pressed in education mode")
        funcButton2.when_pressed = lambda: set_mode("score")
        funcButton3.when_pressed = lambda: checkFinger()
        funcButton4.when_pressed = lambda: set_mode("secondary")
        mainBtn.when_held = lambda: speak()
    elif current_mode == "score":
        funcButton1.when_pressed = lambda: set_mode("education")
        funcButton2.when_pressed = lambda: print("Already in Score Check Mode")
        funcButton3.when_pressed = lambda: button_tapped("None")
        funcButton4.when_pressed = lambda: set_mode("secondary")
    elif current_mode == "secondary":
        funcButton1.when_pressed = lambda: set_mode("wifi")
        funcButton2.when_pressed = lambda: set_mode("battery")
        funcButton3.when_pressed = lambda: set_mode("language")
        funcButton4.when_pressed = lambda: set_mode("main")
    elif current_mode == "wifi":
        funcButton1.when_pressed = lambda: print("Already in Wifi Mode")
        funcButton2.when_pressed = lambda: set_mode("battery")
        funcButton3.when_pressed = lambda: set_mode("language")
        funcButton4.when_pressed = lambda: set_mode("main")
    elif current_mode == "battery":
        funcButton1.when_pressed = lambda: set_mode("wifi")
        funcButton2.when_pressed = lambda: print("Already in Battery Mode")
        funcButton3.when_pressed = lambda: set_mode("language")
        funcButton4.when_pressed = lambda: set_mode("main")
    elif current_mode == "language":
        funcButton1.when_pressed = lambda: set_mode("wifi")
        funcButton2.when_pressed = lambda: set_mode("battery")
        funcButton3.when_pressed = lambda: print("Already in Language Mode")
        funcButton4.when_pressed = lambda: set_mode("main")

def scoreCheckMode():
    global current_mode
    current_mode = "score"
    print("Score Check Mode")
    TTS("Score Check Mode")
    vibrate(0.5)
    if not camera_active:
        if initialize_camera():
            TTS("Camera initialized for score check mode")
        else:
            TTS("Failed to initialize camera")

def mainFunctions():
    global current_mode
    current_mode = "main"
    print("Main Functions")
    TTS("Main Functions")
    vibrate(0.5)
    # Don't stop camera in main mode anymore

def secondaryMode():
    global current_mode
    current_mode = "secondary"
    print("Secondary Mode")
    vibrate(0.5)
    # Don't stop camera in secondary mode anymore

def wifiMode():
    global current_mode
    current_mode = "wifi"
    print("Wifi Mode")
    vibrate(0.5)
    if not camera_active:
        if initialize_camera():
            TTS("Camera initialized for wifi mode")
        else:
            TTS("Failed to initialize camera")

def batteryMode():
    global current_mode
    current_mode = "battery"
    print("Battery Mode")
    vibrate(0.5)
    # Don't stop camera in battery mode anymore

def languageMode():
    global current_mode
    current_mode = "language"
    print("Language Mode")
    vibrate(0.5)
    # Don't stop camera in language mode anymore

def checkFinger():
    """Print the currently touched letter when button 3 is pressed"""
    global current_touched_letter
    if current_touched_letter:
        print(f"Currently touching letter: {current_touched_letter}")
    else:
        print("Not touching any letter")

def speak():
    """Record audio while button is held and process speech-to-text"""
    transcript = ""
    audio_data = []

    # Record audio while button is held
    while mainBtn.is_held:
        print("Holding")
        frame = sd.rec(int(0.5 * fs), samplerate=fs, channels=1, dtype='int16')
        sd.wait()
        audio_data.append(frame)

    if not audio_data:
        return

    # Concatenate recorded chunks 
    audio_data = np.concatenate(audio_data, axis=0)

    # Resample using fast method
    audio_resampled = resample_poly(audio_data.flatten(), target_fs, fs)
    audio_resampled = audio_resampled.astype('int16')

    # Save WAV file
    write(filename, target_fs, audio_resampled)
    print(f"Saved to {filename}")

    # Google Speech-to-Text
    with open(filename, "rb") as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio(content=content)

    try:
        response = client.recognize(config=config, audio=audio)
        for result in response.results:
            transcript = result.alternatives[0].transcript
            print("Transcript:", transcript)
            CheckForKeywords(transcript)

    except Exception as e:
        print("Google transcription error:", e)

    # Clean up
    if os.path.exists(filename):
        os.remove(filename)

def get_best_match(prompt: str, threshold=0.65):
    """Find the best matching command from the prompt maps"""
    prompt = prompt.lower()
    # Combine all prompt maps
    ALL_PROMPTS = {**MAIN_PROMPT_MAP, **COMMON_PROMPT_MAP, **EDUCATION_PROMPT_MAP, **QUIZ_PROMPT_MAP}
    best_match = difflib.get_close_matches(prompt, ALL_PROMPTS.keys(), n=1, cutoff=threshold)
    if best_match:
        print(f"Matched prompt: {best_match[0]}")
        return ALL_PROMPTS[best_match[0]]
    print(f"No match found for prompt: {prompt}")
    return None

def handle_command(flag):
    """Handle different command flags"""
    if not flag:
        return
        
    print(f"Handling command: {flag}")
    match flag:
        case "LEARN_MODE":
            print("Entering learning mode")
            TTS("Entering learning mode. Touch the braille letters to learn them.")
        case "QUIZ_MODE":
            print("Entering quiz mode")
            TTS("Entering quiz mode. I'll ask you to identify letters.")
        case "OBJECT_DETECTION":
            TTS("Object detection mode is not available in this version.")
        case "DISTANCE_CHECK":
            TTS("Distance check mode is not available in this version.")
        case "DESCRIBE_LETTER":
            TTS("Touch a letter to learn about it.")
        case "REPEAT_DESCRIPTION":
            TTS("Touch a letter to hear its description again.")
        case "ANSWER":
            TTS("Please touch the letter you think is correct.")
        case "CONFIRM":
            TTS("Correct!")
        case "DENY":
            TTS("Let's try another letter.")
        case "GREET":
            TTS("Hello! How can I help you today?")
        case "STATE_MODE":
            TTS("You are in main mode.")
        case "TIME_QUERY":
            current_time = time.strftime("%I:%M %p")
            TTS(f"The current time is {current_time}")
        case "DATE_QUERY":
            current_date = time.strftime("%B %d, %Y")
            TTS(f"Today is {current_date}")
        case "CANCEL":
            TTS("Returning to main mode.")
        case _:
            TTS("I don't understand that command.")

def CheckForKeywords(text):
    """Check the transcribed text for keywords and handle commands"""
    if not text:
        return
        
    print(f"Checking keywords for: {text}")
    command_flag = get_best_match(text)
    if command_flag:
        print(f"Found command: {command_flag}")
        handle_command(command_flag)
    else:
        print("No matching command found")
        TTS("Sorry, I didn't understand that. Try saying 'help me' or 'teach me braille'.")

def set_mode(new_mode):
    """Set the current mode and update button actions"""
    global current_mode, state
    
    # If we're in education mode, clean up its processes
    if current_mode == "education":
        print("Cleaning up education mode processes...")
        # Reset education mode specific states
        state.active_learn_mode = False
        state.active_quiz_mode = False
        # Clear braille positions and any ongoing processes
        state.braille_positions = []
        state.marker_corners = None
        state.base_marker_center = None
    
    print(f"Switching from {current_mode} to {new_mode}")
    current_mode = new_mode
    
    # Call the appropriate mode function
    if new_mode == "main":
        mainFunctions()
    elif new_mode == "education":
        educationMode()
    elif new_mode == "score":
        scoreCheckMode()
    elif new_mode == "secondary":
        secondaryMode()
    elif new_mode == "wifi":
        wifiMode()
    elif new_mode == "battery":
        batteryMode()
    elif new_mode == "language":
        languageMode()
    
    # Update button actions for the new mode
    setup_button_actions()

def draw_axes_and_info(frame, marker_corners, camera_matrix, dist_coeffs, marker_size, axis_points, marker_id):
    # Define the marker points in 3D space
    marker_points = np.array([
        [-marker_size/2, marker_size/2, 0],
        [marker_size/2, marker_size/2, 0],
        [marker_size/2, -marker_size/2, 0],
        [-marker_size/2, -marker_size/2, 0]
    ], dtype=np.float32)
    
    # Calculate pose
    ret, rvec, tvec = cv2.solvePnP(
        marker_points,
        marker_corners,
        camera_matrix,
        dist_coeffs
    )
    
    # Calculate distance
    distance = np.linalg.norm(tvec)
    
    # Get rotation matrix from rotation vector
    rot_matrix, _ = cv2.Rodrigues(rvec)
    
    # Project the coordinate axes onto the image
    imgpts, jac = cv2.projectPoints(axis_points, rvec, tvec, camera_matrix, dist_coeffs)
    origin = tuple(map(int, imgpts[0].ravel()))
    x_axis = tuple(map(int, imgpts[1].ravel()))
    y_axis = tuple(map(int, imgpts[2].ravel()))
    z_axis = tuple(map(int, imgpts[3].ravel()))
    
    # Draw the coordinate axes
    cv2.line(frame, origin, x_axis, (0, 0, 255), 3)  # X-axis in red
    cv2.line(frame, origin, y_axis, (0, 255, 0), 3)  # Y-axis in green
    cv2.line(frame, origin, z_axis, (255, 0, 0), 3)  # Z-axis in blue
    
    # Add labels for the axes
    cv2.putText(frame, 'X', x_axis, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    cv2.putText(frame, 'Y', y_axis, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    cv2.putText(frame, 'Z', z_axis, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
    
    # Calculate center of the marker
    center = np.mean(marker_corners, axis=0)
    center_point = (int(center[0]), int(center[1]))
    
    if marker_id == 5:
        # Get Euler angles in degrees
        angles = np.degrees(rvec)
        z_angle = abs(angles[2][0])  # Use absolute value of Z rotation angle
        y_angle = angles[1][0]  # Y rotation angle
        
        # Base Y offset (reduced by half)
        base_y_offset = 0.03  # 3cm base offset in 3D space along Y
        
        # Create interaction point in 3D space
        if z_angle > 25 or y_angle < -30:
            # When absolute Z is above 25 degrees or Y is below -30 degrees, use both Y and Z offsets
            z_offset_3d = -0.06  # 6cm offset in 3D space along Z (negative for upward)
            # Increase Y offset when using Z offset to normalize the distance (reduced by half)
            y_offset_3d = base_y_offset * 1.5  # 4.5cm Y offset (1.5 * 3cm)
            interaction_point_3d = np.array([0, y_offset_3d, z_offset_3d], dtype=np.float32)
        else:
            # When absolute Z is between 0 and 25 degrees and Y is above -30 degrees, only use Y offset
            interaction_point_3d = np.array([0, base_y_offset, 0], dtype=np.float32)
        
        # Transform the interaction point using the marker's rotation and translation
        interaction_point_3d_rotated = np.dot(rot_matrix, interaction_point_3d)
        interaction_point_3d_translated = interaction_point_3d_rotated + tvec.ravel()
        
        # Project the 3D interaction point to 2D
        interaction_point_2d, _ = cv2.projectPoints(
            interaction_point_3d_translated.reshape(1, 1, 3),
            np.zeros(3, dtype=np.float32),
            np.zeros(3, dtype=np.float32),
            camera_matrix,
            dist_coeffs
        )
        
        interaction_point = (int(interaction_point_2d[0][0][0]), int(interaction_point_2d[0][0][1]))
        
        # Draw the interaction pointer (larger circle)
        cv2.circle(frame, interaction_point, 10, (0, 255, 255), -1)  # Yellow circle for interaction pointer
        
        # Draw a line from marker center to interaction point
        cv2.line(frame, center_point, interaction_point, (0, 255, 255), 2)
        
        return interaction_point
    
    return center_point

def process_frames(frame_queue):
    """Process frames in a separate thread"""
    global current_mode, picam2
    
    try:
        print("Getting camera parameters...")
        width = 1280
        height = 720
        print(f"Using fixed resolution: {width}x{height}")
        
        # Create camera matrix with proper focal length
        focal_length = max(width, height)
        camera_matrix = np.array([
            [focal_length, 0, width/2],
            [0, focal_length, height/2],
            [0, 0, 1]
        ], dtype=np.float32)
        print("Camera matrix created")
        
        # Initialize distortion coefficients
        dist_coeffs = np.zeros(5, dtype=np.float32)
        
        # Define the marker size in meters (5cm)
        marker_size = 0.05
        
        # Define the coordinate axes points for visualization
        axis_length = 0.1  # Length of the axes in meters
        axis_points = np.float32([[0, 0, 0],
                                [axis_length, 0, 0],
                                [0, axis_length, 0],
                                [0, 0, axis_length]])
        print("Initialized marker detection parameters")
        
        center_history = []
        current_marker_center = None
        
        print("Starting frame processing loop...")
        frame_count = 0
        last_frame_time = time.time()
        target_fps = 8  # Target 8 FPS
        frame_interval = 1.0 / target_fps  # Time between frames
        
        while camera_active:  # Run as long as camera is active
            try:
                current_time = time.time()
                frame_count += 1
                
                # Capture frame
                frame = picam2.capture_array()
                if frame is None:
                    continue
                
                # Process markers and get interaction point
                current_marker_center, interaction_point = process_marker_detection(
                    frame, camera_matrix, dist_coeffs, marker_size, axis_points
                )
                
                # Update center history
                if current_marker_center:
                    center_history.append(current_marker_center)
                    if len(center_history) > 15:
                        center_history.pop(0)
                
                # Check for finger interaction with braille positions
                if current_marker_center and interaction_point and current_mode == "education" and state.braille_positions:
                    check_finger_interaction(frame, interaction_point, state.braille_positions, current_marker_center)
                
                # Put frame in queue
                try:
                    frame_queue.put_nowait(frame)
                except Full:
                    pass  # Skip frame if queue is full
                
                # Calculate and print FPS every 8 frames
                if frame_count % 8 == 0:
                    fps = 8 / (current_time - last_frame_time)
                    print(f"Processing FPS: {fps:.2f}")
                    last_frame_time = current_time
                
                # Sleep to maintain target FPS
                sleep_time = frame_interval - (time.time() - current_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                print(f"Error in frame processing: {e}")
                continue
                
    except Exception as e:
        print(f"Error in frame processing thread: {e}")

def main():
    try:
        # Start volume control in a separate thread
        threading.Thread(target=volumeControl, daemon=True).start()
        
        # Initialize camera at startup
        print("Starting camera initialization...")
        if initialize_camera():
            print("Camera initialized at startup")
            TTS("Camera initialized")
        else:
            print("Failed to initialize camera at startup")
            TTS("Failed to initialize camera")
        
        # Start in main mode
        set_mode("main")
        
        while True:
            # Check for button presses in the main loop
            if current_mode == "education":
                if funcButton2.is_pressed:
                    set_mode("score")
                elif funcButton4.is_pressed:
                    set_mode("secondary")
            time.sleep(0.1)  # Small delay to prevent CPU overuse
            
    except KeyboardInterrupt:
        print("\nExiting program...")
        TTS("Exiting program")
    except Exception as e:
        print(f"Error in main loop: {e}")
        TTS("An error occurred")
    finally:
        # Cleanup
        vibration_module.off()
        stop_camera()
        sys.exit(0)

if __name__ == "__main__":
    main()
