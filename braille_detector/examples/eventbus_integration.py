#!/usr/bin/env python3
"""
Advanced Braille Detection Integration Example

This example demonstrates how to integrate the Braille Detector module
with the existing EventBus system for real-time braille letter detection.
"""

import asyncio
import sys
import os
import numpy as np
import json

# Dynamic path resolution for security
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.append(PROJECT_ROOT)

try:
    from core.event_bus import EventBus
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

try:
    # Import the compiled C++ module
    import braille_detector_native as bd
except ImportError as e:
    print(f"Failed to import braille_detector_native: {e}")
    print("Please ensure the module is compiled and installed.")
    sys.exit(1)

class BrailleDetectionService:
    """EventBus-integrated Braille detection service"""
    
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.detector = bd.BrailleDetector()
        self.frame_count = 0
        self.detection_enabled = False
        
        # Subscribe to events
        self.bus.subscribe("frame_ready", self.on_frame_ready)
        self.bus.subscribe("start_braille_detection", self.start_detection)
        self.bus.subscribe("stop_braille_detection", self.stop_detection)
        self.bus.subscribe("toggle_debug_mode", self.toggle_debug)
        self.bus.subscribe("start_calibration", self.start_calibration)
        
        # Try to load existing configuration
        self.load_or_create_config()
        
        print("[BrailleDetectionService] Initialized with EventBus integration")
    
    def load_or_create_config(self):
        """Load configuration or create default one"""
        config_file = os.path.join("config", "braille_config.json")
        
        if os.path.exists(config_file):
            try:
                self.detector.load_config(config_file)
                print(f"[BrailleDetectionService] Loaded config from {config_file}")
            except Exception as e:
                print(f"[BrailleDetectionService] Failed to load config: {e}")
                self.create_default_config(config_file)
        else:
            print(f"[BrailleDetectionService] Creating default config at {config_file}")
            self.create_default_config(config_file)
    
    def create_default_config(self, config_file):
        """Create and save default configuration"""
        # Create config directory if it doesn't exist
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        # Configure detector with reasonable defaults
        config = bd.Config()
        config.min_confidence = 0.8
        config.fingertip_offset_ratio = -0.35
        config.debug_mode = False  # Start with debug off
        config.debounce_ms = 200
        config.stability_frames = 2
        
        self.detector.set_config(config)
        self.detector.save_config(config_file)
    
    async def on_frame_ready(self, data):
        """Handle incoming frame_ready events"""
        if not self.detection_enabled:
            return
        
        try:
            frame = data.get("frame")
            if frame is None:
                return
            
            self.frame_count += 1
            
            # Convert frame to numpy array (BGR format expected)
            if isinstance(frame, np.ndarray):
                frame_array = frame
            else:
                frame_array = np.array(frame, dtype=np.uint8)
            
            # Process frame through braille detector
            result = self.detector.process_frame(
                frame_id=self.frame_count,
                timestamp=data.get("timestamp", 0.0),
                frame_array=frame_array
            )
            
            # Handle detection results
            if result.status == "ok":
                await self.on_letter_detected(result, data)
            elif result.status == "calibrating":
                await self.on_calibration_update(result, data)
            else:
                # Handle other statuses (marker_not_found, low_confidence, etc.)
                if self.frame_count % 30 == 0:  # Log every 30th frame
                    await self.bus.publish("detection_status", {
                        "frame_id": self.frame_count,
                        "status": result.status,
                        "confidence": result.confidence
                    })
            
            # Always publish debug image if debug mode is enabled
            if self.detector.get_config().debug_mode and not np.array(result.debug_image).size == 0:
                await self.bus.publish("debug_image", {
                    "frame_id": self.frame_count,
                    "timestamp": data.get("timestamp", 0.0),
                    "image": result.debug_image,
                    "source": "braille_detector"
                })
                
        except Exception as e:
            print(f"[BrailleDetectionService] Error processing frame: {e}")
            await self.bus.publish("braille_error", {
                "error": str(e),
                "frame_id": self.frame_count
            })
    
    async def on_letter_detected(self, result, frame_data):
        """Handle successful letter detection"""
        letter_data = {
            "frame_id": self.frame_count,
            "timestamp": frame_data.get("timestamp", 0.0),
            "letter": result.letter,
            "confidence": result.confidence,
            "bbox": result.bbox,  # [x, y, w, h]
            "dot_mask": result.dot_mask,
            "status": result.status
        }
        
        # Publish braille letter event
        await self.bus.publish("braille_letter", letter_data)
        
        # Also publish a simpler event for TTS
        await self.bus.publish("letter_detected", {
            "letter": result.letter,
            "confidence": result.confidence,
            "timestamp": self.frame_count
        })
        
        print(f"[BrailleDetectionService] Detected letter: {result.letter} "
              f"(confidence: {result.confidence:.2f})")
    
    async def on_calibration_update(self, result, frame_data):
        """Handle calibration progress"""
        if self.frame_count % 10 == 0:  # Log every 10th calibration frame
            await self.bus.publish("calibration_progress", {
                "frame_id": self.frame_count,
                "status": "calibrating",
                "message": "Place marker on reference braille cell..."
            })
    
    async def start_detection(self, data):
        """Start braille detection"""
        self.detection_enabled = True
        self.frame_count = 0
        
        await self.bus.publish("tts", {
            "text": "Braille detection activated"
        })
        
        print("[BrailleDetectionService] Braille detection started")
    
    async def stop_detection(self, data):
        """Stop braille detection"""
        self.detection_enabled = False
        
        await self.bus.publish("tts", {
            "text": "Braille detection deactivated"
        })
        
        print("[BrailleDetectionService] Braille detection stopped")
    
    async def toggle_debug(self, data):
        """Toggle debug mode"""
        enabled = data.get("enabled", True)
        self.detector.toggle_debug(enabled)
        
        message = f"Debug mode {'enabled' if enabled else 'disabled'}"
        await self.bus.publish("tts", {"text": message})
        
        print(f"[BrailleDetectionService] {message}")
    
    async def start_calibration(self, data):
        """Start calibration process"""
        print("[BrailleDetectionService] Starting calibration...")
        
        # Stop normal detection during calibration
        detection_enabled_backup = self.detection_enabled
        self.detection_enabled = True
        
        try:
            self.detector.start_calibration()
            
            await self.bus.publish("tts", {
                "text": "Calibration started. Place the ArUco marker on a reference braille cell."
            })
            
            await self.bus.publish("calibration_started", {
                "message": "Place marker on reference braille cell"
            })
            
            # Wait for calibration to complete
            await asyncio.sleep(5)  # Simulate calibration time
            
            self.detector.end_calibration()
            
            if self.detector.is_calibrated():
                await self.bus.publish("tts", {
                    "text": "Calibration completed successfully"
                })
                
                await self.bus.publish("calibration_completed", {
                    "success": True
                })
            else:
                await self.bus.publish("tts", {
                    "text": "Calibration failed. Please try again."
                })
                
                await self.bus.publish("calibration_completed", {
                    "success": False
                })
        
        finally:
            # Restore original detection state
            self.detection_enabled = detection_enabled_backup

async def main():
    """Main application entry point"""
    print("=== Advanced Braille Detection Service ===")
    
    # Initialize EventBus
    bus = EventBus()
    
    # Initialize services
    braille_service = BrailleDetectionService(bus)
    
    # Add TTS simulation
    async def simulate_tts(data):
        text = data.get("text", "")
        print(f"[TTS] {text}")
    
    bus.subscribe("tts", simulate_tts)
    
    # Add letter detection logging
    async def log_letter_detection(data):
        letter = data.get("letter", "")
        confidence = data.get("confidence", 0.0)
        print(f"[Detection] Letter: {letter} (confidence: {confidence:.2f})")
    
    bus.subscribe("letter_detected", log_letter_detection)
    
    # Start detection
    await braille_service.start_detection({})
    
    print("[Main] Service ready. Use EventBus to interact with the detector:")
    print("  - start_braille_detection: Enable detection")
    print("  - stop_braille_detection: Disable detection")  
    print("  - toggle_debug_mode: Enable/disable debug visualization")
    print("  - start_calibration: Run calibration routine")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n[Main] Interrupted by user")
    finally:
        await braille_service.stop_detection({})
    
    print("[Main] Application terminated")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Main] Interrupted")
    except Exception as e:
        print(f"[Main] Error: {e}")
        sys.exit(1)
