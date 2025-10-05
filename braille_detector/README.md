# Advanced Braille Detection Module

A high-performance C++ module for detecting Braille letters in real-time using ArUco marker-based fingertip tracking and OpenCV-based image processing.

## Features

- **ArUco Marker Tracking**: Uses marker ID 4 for precise fingertip localization
- **Real-time Processing**: Optimized for Raspberry Pi 5 with ~20fps performance
- **Braille Dot Detection**: Advanced blob detection with adaptive thresholding
- **Letter Mapping**: Complete a-z Braille alphabet support (uncontracted)
- **Calibration System**: Learn braille cell dimensions from reference positions
- **Debug Mode**: Visual debugging with ROI overlay and dot visualization
- **EventBus Integration**: Seamless integration with Python asyncio EventBus system
- **Thread-Safe**: Concurrent access with mutex protection

## Architecture

```
Input: frame_ready event
├── ArUco Detection (marker ID 4)
├── Fingertip Calculation (relative offset)
├── ROI Extraction (2-3x braille cell size)
├── Preprocessing (CLAHE + bilateral + adaptive threshold)
├── Dot Detection (SimpleBlobDetector)
├── Grid Mapping (3x2 braille pattern)
├── Letter Mapping (6-bit mask → ASCII)
├── Confidence Scoring (coherency + stability)
└── Output: braille_letter event
```

## Installation

### Dependencies

```bash
# Ubuntu/Debian (Raspberry Pi)
sudo apt-get update
sudo apt-get install -y \
    cmake \
    g++ \
    libopencv-dev \
    libopencv-contrib-dev \
    python3-dev \
    python3-pip \
    nlohmann-json3-dev

pip3 install pybind11 numpy opencv-python asyncio
```

### Build

```bash
cd braille_detector
mkdir build && cd build
cmake ..
make -j4
```

## Usage

### Python Integration

```python
import numpy as np
import asyncio
from braille_detector_native import BrailleDetector

# Initialize detector
detector = BrailleDetector()

# Load configuration
detector.load_config("config/braille_calib.json")

# Process frame
frame = np.array(camera_frame, dtype=np.uint8)  # BGR image
result = detector.process_frame(0, timestamp, frame)

if result.status == "ok":
    print(f"Detected letter: {result.letter} (confidence: {result.confidence})")
else:
    print(f"Detection failed: {result.status}")
```

### EventBus Integration

```python
# In your main event bus handler
async def on_frame_ready(data):
    frame = data["frame"]
    frame_id = data["frame_id"]
    timestamp = data["timestamp"]
    
    # Convert to numpy array
    frame_array = np.array(frame, dtype=np.uint8)
    
    # Process with Braille detector
    result = detector.process_frame(frame_id, timestamp, frame_array)
    
    if result.status == "ok":
        # Publish braille letter event
        await bus.publish("braille_letter", {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "letter": result.letter,
            "confidence": result.confidence,
            "bbox": result.bbox,
            "dot_mask": result.dot_mask,
            "status": result.status
        })
        
        # Optionally publish debug image
        if detector.get_config().debug_mode:
            await bus.publish("debug_image", {
                "frame_id": frame_id,
                "timestamp": timestamp,
                "image": result.debug_image
            })
```

### Calibration

```python
# Interactive calibration
detector.start_calibration()

# Place marker at reference braille cell
frame = camera.read()
frame_array = np.array(frame, dtype=np.uint8)
detector.perform_calibration(frame_array)

detector.end_calibration()

# Check calibration status
if detector.is_calibrated():
    print("Calibration successful!")
else:
    print("Calibration failed!")
```

### Configuration

```python
# Create custom configuration
config = Config()
config.min_confidence = 0.85
config.fingertip_offset_ratio = -0.35
config.debug_mode = True
config.aruco_marker_id = 4

detector.set_config(config)
detector.save_config("my_config.json")
```

## Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_confidence` | 0.8 | Minimum confidence threshold for output |
| `fingertip_offset_ratio` | -0.35 | Relative Y offset from marker center |
| `debounce_ms` | 200 | Debounce time for same letter output |
| `stability_frames` | 2 | Frames to consider for stability |
| `debug_mode` | false | Enable visual debug output |
| `debug_dir` | "./debug" | Directory for debug images |
| `aruco_marker_id` | 4 | ArUco marker ID to track |
| `roi_scaling_factor` | 2.5 | ROI size relative to marker |

## Braille Letter Mapping

The module supports standard uncontracted literary Braille (a-z):

```
a: 100000 (dot 1 only)
b: 110000 (dots 1,2)
c: 100100 (dots 1,4)
...
z: 111101 (dots 1,3,4,5,6)
```

## Performance Characteristics

- **Latency**: < 100ms per frame on Raspberry Pi 5
- **Accuracy**: > 85% with proper calibration
- **Throughput**: 10-15 fps sustained processing
- **Memory**: ~50MB base overhead, +10MB per frame

## Debug Mode

When enabled, debug mode provides:

- ArUco marker visualization
- ROI bounding boxes  
- Detected dot overlays
- 3x2 grid overlay
- Confidence scores
- Saved debug images to `debug_dir`

## Error Codes

| Status | Description |
|--------|-------------|
| `ok` | Successful detection |
| `marker_not_found` | ArUco marker not detected |
| `no_dots_detected` | No braille dots found in ROI |
| `no_mapping` | Dot pattern not recognized |
| `low_confidence` | Below confidence threshold |
| `roi_out_of_bounds` | Fingertip position invalid |
| `calibrating` | Currently in calibration mode |

## Troubleshooting

### Marker Detection Issues
- Ensure marker ID 4 is clearly visible
- Check marker dictionary (DICT_6X6_250)
- Verify lighting conditions

### Poor Dot Detection
- Run calibration routine
- Adjust adaptive threshold parameters
- Check braille material contrast

### Low Confidence Scores
- Validate calibration data
- Check stability_frames setting
- Verify ROI placement accuracy

## API Reference

### BrailleDetector Class

#### Methods
- `process_frame(frame_id, timestamp, frame_array)`: Process single frame
- `detect_letter(frame_array)`: Simple letter detection
- `load_config(filename)`: Load configuration from JSON
- `save_config(filename)`: Save configuration to JSON
- `start_calibration()`: Enter calibration mode
- `end_calibration()`: Exit calibration mode
- `is_calibrated()`: Check calibration status
- `perform_calibration(frame_array)`: Run calibration
- `toggle_debug(enabled)`: Enable/disable debug mode

#### Properties
- `Config`: Configuration parameters
- `CalibrationData`: Calibration measurements
- `BrailleResult`: Detection results

## License

This project is part of the AEye assistive technology system. See main project license for details.

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/new-feature`)
3. Commit changes (`git commit -am 'Add new feature'`)
4. Push to branch (`git push origin feature/new-feature`)
5. Create Pull Request

## Support

For technical support or bug reports, please file an issue in the main AEye repository.
