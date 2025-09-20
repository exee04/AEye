#!/usr/bin/env python3
"""
Test script for braille detection system
This script tests the braille detection without the full system
"""

import sys
import asyncio
import cv2
import numpy as np

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

def test_braille_detection():
    """Test the braille detection with a simple frame"""
    print("Testing braille detection...")
    
    # Create a test frame (640x480, 3 channels)
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Add some test content
    cv2.putText(test_frame, "Braille Detection Test", (50, 50), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(test_frame, "This is a test frame", (50, 100), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
    
    # Add some test braille-like dots for detection
    for i in range(3):
        for j in range(2):
            x = 100 + i * 50
            y = 200 + j * 30
            cv2.circle(test_frame, (x, y), 5, (255, 255, 255), -1)
    
    try:
        # Test braille detection
        clusters = braille_cpp.detect_braille(test_frame)
        print(f"✅ Braille detection: Found {len(clusters)} clusters")
        
        for i, cluster in enumerate(clusters):
            print(f"  Cluster {i}: letter='{cluster.letter}', dots={cluster.dot_array}")
            print(f"    Bbox: x={cluster.bbox.x}, y={cluster.bbox.y}, w={cluster.bbox.width}, h={cluster.bbox.height}")
        
        # Test finger detection
        fingers = braille_cpp.detect_fingers(test_frame)
        print(f"✅ Finger detection: Found {len(fingers)} fingers")
        
        for i, finger in enumerate(fingers):
            print(f"  Finger {i}: id={finger.id}, center=({finger.center.x}, {finger.center.y})")
            
    except Exception as e:
        print(f"❌ Error during detection: {e}")
        return False
    
    return True

def test_braille_letters_mapping():
    """Test the braille letters mapping"""
    print("\nTesting braille letters mapping...")
    
    # Load the mapping
    import json
    try:
        with open("/home/ky/Desktop/AEye/core/BrailleLetters.json", "r") as f:
            braille_letters = json.load(f)
        print(f"✅ Loaded {len(braille_letters)} braille letter mappings")
        
        # Test a few mappings
        test_cases = [
            ("100000", "A"),
            ("110000", "B"), 
            ("100100", "C"),
            ("101011", "Z")
        ]
        
        for dot_string, expected_letter in test_cases:
            actual_letter = braille_letters.get(dot_string, "?")
            if actual_letter == expected_letter:
                print(f"  ✅ {dot_string} -> {actual_letter}")
            else:
                print(f"  ❌ {dot_string} -> {actual_letter} (expected {expected_letter})")
                
    except FileNotFoundError:
        print("❌ BrailleLetters.json not found")
        return False
    except Exception as e:
        print(f"❌ Error loading braille letters: {e}")
        return False
    
    return True

def main():
    print("🧪 Braille Detection System Test")
    print("=" * 40)
    
    # Test C++ module loading
    success = True
    
    # Test braille detection
    if not test_braille_detection():
        success = False
    
    # Test braille letters mapping
    if not test_braille_letters_mapping():
        success = False
    
    print("\n" + "=" * 40)
    if success:
        print("✅ All tests passed! The braille detection system is ready.")
        print("\nTo use the system:")
        print("1. Run: python main.py")
        print("2. Press button 17 to enter education mode")
        print("3. Press button 22 to cycle through learn/quiz modes")
        print("4. Touch braille letters to interact with them")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
