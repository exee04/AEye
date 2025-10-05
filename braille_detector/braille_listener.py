#!/usr/bin/env python3
"""
Example integration of Advanced Braille Detection with existing AEye EventBus

This script demonstrates how to integrate the new C++ Braille Detector 
with the existing Python EventBus system for seamless braille letter detection.
"""

import asyncio
import sys
import os
import cv2
import numpy as np

# Dynamic path resolution for security  
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.append(PROJECT_ROOT)

from core.event_bus import EventBus

try:
    # Import the compiled C++ module
    import braille_detector_native as bd
except ImportError as e:
    print(f"Failed to import braille_detector_native: {e}")
    print("Please ensure the module is compiled:")
    print("  cd braille_detector")
    print("  mkdir build && cd build")
    print("  cmake .. && make")
    sys.exit(1)

class BrailleListener:
    """Integrates C++ Braille Detector with Python EventBus"""
    
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.detector = bd.BrailleDetector()
        self.frame_count = 0
        self.is_active = False
        
        # Subscribe to core events
        self.bus.subscribe("frame_ready", self.on_frame_ready)
        self.bus.subscribe("start_detect", self.start_detection)
        self.bus.subscribe("stop_detect", self.stop_detection)
        
        print("[BrailleListener] Initialized with C++ detector")
    
    async def on_frame_ready(self, data):
        """Process incoming frame_ready events"""
        if not self.is_active:
            return
            
        try:
            frame = data.get("frame")
            if frame is None:
                return
                
            self.frame_count += 1
            
            # Validate frame format
            if not isinstance(frame, np.ndarray):
                frame = np.array(frame, dtype=np.uint8)
            
            # Process with C++ detector
            result = self.detector.detect_letter(frame)
            
            if result:  # Non-empty result means detection
                await self.publish_detection(result, data)
                
        except Exception as e:
            print(f"[BrailleListener] Error processing frame: {e}")
    
    async def publish_detection(self, letter, frame_data):
        """Publish successful detection"""
        detection_data = {
            "frame_id": self.frame_count,
            "timestamp": frame_data.get("timestamp", 0.0),
            "letter": letter,
            "confidence": 0.85,  # Simplified confidence
            "source": "cpp_detector"
        }
        
        # Publish detection event
        await self.bus.publish("braille_letter", detection_data)
        
        # Also publish existing events for compatibility
        await self.bus.publish("letter_selected", {
            "letter": letter,
            "mode": "cpp_detection"
        })
        
        # Optional TTS feedback
        await self.bus.publish("tts", {
            "text": f"The letter is {letter}"
        })
        
        print(f"[BrailleListener] Detected: {letter}")
    
    async def start_detection(self, data):
        """Start braille detection"""
        self.is_active = True
        self.frame_count = 0
        
        await self.bus.publish("tts", {
            "text": "C++ Braille detection activated"
        })
        
        print("[BrailleListener] Detection started")
    
    async def stop_detection(self, data):
        """Stop braille detection"""  
        self.is_active = False
        
        await self.bus.publish("tts", {
            "text": "Braille detection deactivated"
        })
        
        print("[BrailleListener] Detection stopped")

class MockCamera:
    """Simple mock camera for testing"""
    
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.running = False
        
    async def start(self):
        """Start sending mock frames"""
        self.running = True
        frame_count = 0
        
        while self.running:
            # Create mock frame with ArUco marker and braille dots
            frame = self.create_mock_frame(frame_count)
            
            await self.bus.publish("frame_ready", {
                "frame": frame,
                "frame_id": frame_count,
                "timestamp": frame_count / 30.0
            })
            
            frame_count += 1
            await asyncio.sleep(1.0 / 30)  # 30 fps
    
    def create_mock_frame(self, frame_id):
        """Create a mock frame with various braille patterns"""
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        
        # Add ArUco marker simulation (white square)
        cv2.rectangle(frame, (100, 100), (140, 140), (255, 255, 255), -1)
        
        # Cycle through different braille letters
        pattern = frame_id % 100
        if pattern < 30:
            # Letter 'a' pattern
            cv2.circle(frame, (120, 180), 2, (0, 0, 0), -1)
        elif pattern < 60:
            # Letter 'b' pattern  
            cv2.circle(frame, (120, 180), 2, (0, 0, 0), -1)
            cv2.circle(frame, (120, 200), 2, (0, 0, 0), -1)
        else:
            # Letter 'c' pattern
            cv2.circle(frame, (120, 180), 2, (0, 0, 0), -1)
            cv2.circle(frame, (130, 180), 2, (0, 0, 0), -1)
        
        return frame
    
    def stop(self):
        """Stop mock camera"""
        self.running = False

async def main():
    """Main application entry point"""
    print("=== AEye Braille Detection Integration ===")
    
    # Initialize EventBus
    bus = EventBus()
    
    # Initialize services
    braille_listener = BrailleListener(bus)
    
    # Add simple TTS handler
    async def tts_handler(data):
        text = data.get("text", "")
        print(f"[TTS] {text}")
    
    bus.subscribe("tts", tts_handler)
    
    # Start detection
    await braille_listener.start_detection({})
    
    # Create mock camera for testing
    mock_camera = MockCamera(bus)
    camera_task = asyncio.create_task(mock_camera.start())
    
    print("[Main] Integration ready!")
    print("  - Listening for 'frame_ready' events")
    print("  - Publishing 'braille_letter' detections")
    print("  - Press Ctrl+C to stop")
    
    try:
        # Run for 60 seconds
        await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\n[Main] Interrupted by user")
    finally:
        # Cleanup
        mock_camera.stop()
        await braille_listener.stop_detection({})
        
        if not camera_task.done():
            camera_task.cancel()
            try:
                await camera_task
            except asyncio.CancelledError:
                pass
    
    print("[Main] Application terminated")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Main] Interrupted")
    except Exception as e:
        print(f"[Main] Error: {e}")
        sys.exit(1)
