# Quick Integration Guide: Advanced Braille Detection

## Immediate Setup (5 minutes)

### 1. Check Prerequisites
```bash
# Verify OpenCV is installed
python3 -c "import cv2; print('OpenCV version:', cv2.__version__)"

# Check if ArUco is available
python3 -c "import cv2.aruco as aruco; print('ArUco available')"
```

### 2. Build the C++ Module
```bash
cd braille_detector
mkdir build && cd build
cmake ..
make -j4

# Test basic functionality
python3 -c "
import sys; sys.path.append('.')
import braille_detector_native as bd
detector = bd.BrailleDetector()
print('✓ C++ module ready')
"
```

### 3. Replace Existing Detection (Simple Method)

```bash
# Backup current implementation
cd /home/ky/Desktop/AEye/core
cp BrailleDetect.py BrailleDetect_original.py

# Use the new advanced implementation
cp BrailleDetectAdvanced.py BrailleDetect.py
```

### 4. Test Integration
```bash
# Run the enhanced braille listener
cd /home/ky/Desktop/AEye
python3 braille_detector/braille_listener.py
```

## Advanced Setup (10 minutes)

### 1. Custom Configuration
```python
# Create optimized configuration
config_file = "config/braille_config.json"
config = {
    "min_confidence": 0.75,
    "fingertip_offset_ratio": -0.35,
    "debug_mode": True,
    "aruco_marker_id": 4,
    "roi_scaling_factor": 2.5
}

with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)
```

### 2. Integration with Existing Mode
```python
# In main.py or education mode
from core.BrailleDetectAdvanced import BrailleDetectAdvanced

# Replace or enhance existing BrailleDetect
braille_detector = BrailleDetectAdvanced(bus)

# Optional: Subscribe to new events
bus.subscribe("toggle_cpp_debug", braille_detector.toggle_cpp_debug)
bus.subscribe("start_cpp_calibration", braille_detector.start_cpp_calibration)
```

### 3. Calibration Routine
```python
# Trigger calibration via EventBus
await bus.publish("start_cpp_calibration", {
    "instruction": "Place ArUco marker on reference braille cell"
})

# Check calibration status
if braille_detector.cpp_detector.is_calibrated():
    print("✓ Calibration successful")
else:
    print("✗ Calibration needed")
```

## Usage Patterns

### Event-Driven Detection
```python
# The detector automatically subscribes to:
# - "frame_ready" for camera input
# - "start_detect" for activation
# - "stop_detect" for deactivation

# Publishes:
# - "braille_letter" with detection results
# - "debug_image" when debug mode enabled
# - "tts" for audio feedback
```

### Real-time Configuration
```python
# Adjust parameters on the fly
await bus.publish("toggle_cpp_debug", {"enabled": True})

# Switch detection methods
await bus.publish("switch_detection_method", {"method": "cpp"})

# Start calibration
await bus.publish("start_cpp_calibration", {})
```

## Monitoring and Debugging

### Debug Mode
```bash
# Enable debug visualization
echo '{"debug_mode": true}' > config/braille_config.json
python3 braille_detector/braille_listener.py

# Check debug output
ls -la debug/
```

### Status Monitoring
```python
# Monitor detection events
bus.subscribe("braille_letter", lambda data: print(f"Detected: {data['letter']}"))

# Handle errors
bus.subscribe("braille_error", lambda data: print(f"Error: {data['error']}"))
```

## Performance Tuning

### Raspberry Pi 5 Optimization
```json
{
  "min_confidence": 0.7,
  "stability_frames": 2,
  "debounce_ms": 150,
  "morphology_kernel_size": 3,
  "adaptive_thresh_block_size": 9,
  "roi_scaling_factor": 2.0
}
```

### High Accuracy Mode
```json
{
  "min_confidence": 0.85,
  "stability_frames": 3,
  "debounce_ms": 200,
  "morphology_kernel_size": 5,
  "adaptive_thresh_block_size": 11,
  "roi_scaling_factor": 3.0
}
```

## Troubleshooting Quick Fixes

### ArUco Marker Issues
```bash
# Test marker detection
python3 -c "
import cv2
dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
marker = cv2.aruco.drawMarker(dict, 4, 200)
cv2.imwrite('test_marker.jpg', marker)
print('Marker saved as test_marker.jpg')
"

# Print marker for testing
python3 -c "
import cv2, numpy as np
dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
marker = cv2.aruco.drawMarker(dict, 4, 200)
print('Print this marker (40mm square) and place on braille material')
cv2.imwrite('/tmp/marker_4.jpg', marker)
"
```

### Low Performance
```bash
# Monitor CPU usage
htop

# Check FPS
python3 -c "
import time
import braille_detector_native as bd
import numpy as np

detector = bd.BrailleDetector()
frame = np.random.randint(0,255,(480,640,3),dtype=np.uint8)

times = []
for i in range(50):
    start = time.time()
    result = detector.process_frame(i, time.color(), frame)
    times.append(time.time() - start)

print(f'Avg processing: {sum(times)/len(times)*1000:.1f}ms')
print(f'Estimated FPS: {1/(sum(times)/len(times)):.1f}')
"
```

### Memory Issues
```bash
# Check memory usage
free -h

# Restart services to free memory
sudo systemctl restart camera.service
```

## Validation Checklist

- [ ] OpenCV 4.x installed with contrib modules
- [ ] ArUco marker ID 4 readily available
- [ ] C++ module builds without errors
- [ ] Python bindings load successfully
- [ ] EventBus integration functional
- [ ] Camera provides 640x480 RGB frames
- [ ] Debug mode produces visualization
- [ ] Calibration routine completes
- [ ] Detection produces reasonable letters (a-z)
- [ ] Performance exceeds 10 FPS sustained

## Next Steps

1. **Run Calibration**: Place marker on reference braille cell
2. **Test Detection**: Try various braille letters
3. **Adjust Parameters**: Tune for your specific braille material
4. **Monitor Performance**: Ensure sustained processing rate
5. **Integrate Education**: Connect with learn/quiz modes

## Support Resources

- `BUILD_INSTRUCTIONS.md`: Detailed compilation guide
- `README.md`: Complete feature documentation  
- `SYSTEM_ARCHITECTURE.md`: Technical implementation details
- `tests/test_main.cpp`: Unit test validation
- Debug output directory: `./debug/`

The advanced detector provides significant improvements in accuracy, performance, and robustness compared to the original implementation while maintaining seamless compatibility with the existing AEye system architecture.
