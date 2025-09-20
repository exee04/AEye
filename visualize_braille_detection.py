#!/usr/bin/env python3
"""
Visualization script for braille detection
Similar to detecttest.py but using the C++ hybrid module
"""

import sys
import cv2
import numpy as np
import time
import json

# Add the core path
sys.path.append("/home/ky/Desktop/AEye/core")
sys.path.append("/home/ky/Desktop/AEye/core/BrailleCPPModules/build")

try:
    import braille_cpp
    print("✅ C++ braille module loaded successfully")
except ImportError as e:
    print(f"❌ Failed to load C++ braille module: {e}")
    print("Make sure to build the C++ module first with cmake and make")
    sys.exit(1)

def load_braille_letters():
    """Load braille letter mapping from JSON file"""
    try:
        with open("/home/ky/Desktop/AEye/core/BrailleLetters.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ BrailleLetters.json not found")
        return {}

def draw_braille_visualization(frame, clusters, fingers, braille_letters):
    """Draw braille detection visualization on frame"""
    vis_frame = frame.copy()
    
    # Draw detected braille clusters
    for cluster in clusters:
        x, y, w, h = cluster.bbox.x, cluster.bbox.y, cluster.bbox.width, cluster.bbox.height
        
        # Convert dot array to string for mapping
        dot_string = ''.join(map(str, cluster.dot_array))
        letter = braille_letters.get(dot_string, "?")
        
        # Draw bounding box
        cv2.rectangle(vis_frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
        
        # Draw letter label
        cv2.putText(vis_frame, f"Braille: {letter}", (x, max(10, y - 8)), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Draw individual dots
        for i, dot in enumerate(cluster.dot_array):
            if dot == 1:
                dot_x = x + (i % 2) * (w // 2) + w // 4
                dot_y = y + (i // 2) * (h // 3) + h // 6
                cv2.circle(vis_frame, (dot_x, dot_y), 3, (0, 180, 0), -1)
    
    # Draw detected fingers
    for finger in fingers:
        center_x, center_y = int(finger.center.x), int(finger.center.y)
        cv2.circle(vis_frame, (center_x, center_y), 8, (255, 0, 0), -1)
        cv2.putText(vis_frame, f"Finger {finger.id}", (center_x + 10, center_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
    
    # Add status information
    status_text = f"Detected: {len(clusters)} braille clusters, {len(fingers)} fingers"
    cv2.putText(vis_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    return vis_frame

def main():
    print("🎥 Braille Detection Visualization")
    print("Press 'q' to quit, 's' to save current frame")
    
    # Load braille letters mapping
    braille_letters = load_braille_letters()
    if not braille_letters:
        print("❌ Could not load braille letters mapping")
        return 1
    
    # Initialize camera (try PiCamera2 first, then fallback to cv2)
    camera = None
    using_pi_camera = False
    
    try:
        from picamera2 import Picamera2
        camera = Picamera2()
        config = camera.create_preview_configuration(main={"size": (640, 480)})
        camera.configure(config)
        camera.start()
        using_pi_camera = True
        print("✅ PiCamera2 initialized")
    except ImportError:
        print("⚠️ PiCamera2 not available, trying cv2 webcam...")
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            print("❌ Could not open camera")
            return 1
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print("✅ CV2 webcam initialized")
    except Exception as e:
        print(f"❌ Camera initialization failed: {e}")
        return 1
    
    print("📝 Instructions:")
    print("  - Show braille text to the camera")
    print("  - Use ArUco markers for finger tracking")
    print("  - Press 'q' to quit")
    print("  - Press 's' to save current frame")
    
    frame_count = 0
    start_time = time.time()
    
    try:
        while True:
            if using_pi_camera:
                frame = camera.capture_array()
                # PiCamera2 gives RGB → convert to BGR for OpenCV
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            else:
                ret, frame = camera.read()
                if not ret:
                    print("❌ Failed to read frame from camera")
                    break
            
            # Detect braille clusters
            clusters = braille_cpp.detect_braille(frame)
            
            # Detect fingers
            fingers = braille_cpp.detect_fingers(frame)
            
            # Draw visualization
            vis_frame = draw_braille_visualization(frame, clusters, fingers, braille_letters)
            
            # Add FPS counter
            frame_count += 1
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                print(f"📊 FPS: {fps:.1f}")
            
            # Show frame
            cv2.imshow("Braille Detection Visualization", vis_frame)
            
            # Handle key presses
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("👋 Quitting...")
                break
            elif key == ord('s'):
                filename = f"braille_detection_{int(time.time())}.jpg"
                cv2.imwrite(filename, vis_frame)
                print(f"💾 Saved frame as {filename}")
    
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
    
    finally:
        if using_pi_camera:
            camera.stop()
        else:
            camera.release()
        cv2.destroyAllWindows()
        print("✅ Camera released")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
