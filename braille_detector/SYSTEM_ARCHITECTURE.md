# Advanced Braille Detection System Architecture

## Overview

This document describes the architecture of the advanced C++ Braille detection module that integrates with the AEye assistive technology system. The module provides real-time Braille letter detection using ArUco marker tracking and OpenCV-based computer vision.

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    EVENTBUS ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    │
│  │    Camera   │───▶│  frame_ready │───▶│Braille Detector │    │
│  │ PiCamera2   │    │    event     │    │   Service        │    │
│  └─────────────┘    └──────────────┘    └─────────────────┘    │
│                                │                    │           │
│                                ▼                    ▼           │
│                        ┌──────────────┐    ┌─────────────────┐ │
│                        │Debug Visual  │    │ braille_letter  │ │
│                        │    event     │    │     event       │ │
│                        └──────────────┘    └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Frame Input
- **Source**: PiCamera2 RGB frame (640x480)
- **Format**: `frame_ready` event with structure:
  ```python
  {
    "frame": numpy.ndarray,      # 640x480 BGR image
    "frame_id": int,             # Sequential frame counter
    "timestamp": float           # Epoch milliseconds
  }
  ```

### 2. ArUco Marker Detection
- **Target**: Marker ID 4 for fingertip localization
- **Output**: Marker center coordinates and orientation
- **Fallback**: Returns error if marker not detected

### 3. Fingertip Calculation
- **Method**: Relative offset from marker center
- **Formula**: `fingertip = marker_center + (0, offset_ratio * marker_height)`
- **Default**: `offset_ratio = -0.35` (35% marker height below center)

### 4. ROI Extraction
- **Region**: 2-3x Braille cell size around fingertip
- **Size**: Adaptive based on marker size or calibration data
- **Validation**: Bounds checking against frame dimensions

### 5. Image Preprocessing Pipeline
```
Original ROI → Grayscale → CLAHE → Bilateral Filter → 
Adaptive Threshold → Morphological Operations → Clean Image
```

### 6. Dot Detection
- **Algorithm**: SimpleBlobDetector with parameters:
  - Min Area: 8 pixels
  - Max Area: 150 pixels
  - Min Circularity: 0.7
  - Min Convexity: 0.8
- **Output**: List of 2D dot positions

### 7. Grid Mapping
- **Layout**: 3x2 Braille pattern normalization
- **Conversion**: Dot positions → 6-bit mask
- **Pattern**: Bit positions 0-5 represent dots 1-6

### 8. Letter Recognition
- **Mapping**: 6-bit mask → ASCII letter (a-z)
- **Dictionary**: Standard uncontracted literary Braille
- **Fallback**: Returns '?' for unmapped patterns

### 9. Confidence Assessment
- **Factors**: Dot count consistency, marker stability
- **Threshold**: Configurable minimum (default 0.8)
- **Filtering**: Debounce and duplicate suppression

## Core Classes

### BrailleDetector (C++)
```cpp
class BrailleDetector {
public:
    BrailleResult processFrame(const FrameMsg& msg);
    void setConfig(const Config& config);
    void startCalibration();
    void endCalibration();
    void toggleDebug(bool enabled);
private:
    cv::Point2f detectArUcoMarker(const cv::Mat& frame);
    cv::Rect extractROI(const cv::Point2f& fingertip_pos);
    std::vector<cv::Point2f> detectBrailleDots(const cv::Mat& roi);
    int computeDotMask(const std::vector<cv::Point2f>& dots);
};
```

### PythonIntegration
```python
class PythonBrailleDetector:
    def process_frame(self, frame_id, timestamp, frame_array) -> PythonBrailleResult
    def detect_letter(self, frame_array) -> str
    def load_config(self, filename: str)
    def start_calibration(self)
    def toggle_debug(self, enabled: bool)
```

## Configuration System

### File Format
```json
{
  "min_confidence": 0.8,
  "fingertip_offset_ratio": -0.35,
  "debounce_ms": 200,
  "stability_frames": 2,
  "debug_mode": false,
  "debug_dir": "./debug",
  "aruco_marker_id": 4,
  "roi_scaling_factor": 2.5,
  "morphology_kernel_size": 3,
  "adaptive_thresh_block_size": 11,
  "adaptive_thresh_c": 2,
  "calibration": {
    "dot_spacing_pixels": 12.0,
    "cell_width_pixels": 24.0,
    "cell_height_pixels": 36.0,
    "fingertip_offset": {"x": 0, "y": -17.5},
    "is_calibrated": true
  }
}
```

### Runtime Modification
- **Thread-safe**: Mutex-protected configuration updates
- **Hot-swapping**: Changes apply to next frame
- **Validation**: Parameter bounds checking

## Calibration System

### Interactive Calibration
1. **Initiation**: Event-driven calibration start
2. **Reference**: Place marker on known Braille cell
3. **Measurement**: Compute dot spacing and cell dimensions
4. **Storage**: Save calibration data to JSON
5. **Validation**: Verify calibration parameters

### Calibration Data
- **Dot Spacing**: Average distance between detected dots
- **Cell Dimensions**: Estimated width and height
- **Offset**: Refined fingertip position relative to marker

## Debug and Visualization

### Debug Mode Features
- **ArUco Visualization**: Marker detection overlay
- **ROI Highlighting**: Region of interest bounding boxes
- **Dot Overlays**: Detected dot positions
- **Grid Display**: 3x2 pattern visualization
- **Confidence Scores**: Real-time detection confidence
- **Image Saving**: Debug frames to disk

### Debug Output
```
debug/
├── debug_frame_001_1640995200000.jpg
├── debug_frame_002_1640995200100.jpg
└── debug_frame_003_1640995200200.jpg
```

## Performance Characteristics

### Raspberry Pi 5 Specifications
- **CPU**: ARM Cortex-A76 quad-core
- **Memory**: 8GB LPDDR4X
- **Processing**: ~18ms per frame
- **Throughput**: 15-20 sustained FPS
- **Latency**: 80-100ms end-to-end

### Optimization Strategies
1. **ROI Limiting**: Process only relevant image regions
2. **Adaptive Thresholding**: Efficient contrast enhancement
3. **Morphological Optimization**: Minimal kernel operations
4. **Memory Pooling**: Reuse image buffers
5. **Thread Safety**: Lock-free configuration updates

## Event Integration

### Event Flow
```python
# Input event
{
  "event_type": "frame_ready",
  "data": {
    "frame": numpy.ndarray,
    "frame_id": 12345,
    "timestamp": 1640995200.123
  }
}

# Output events
{
  "event_type": "braille_letter",
  "data": {
    "frame_id": 12345,
    "timestamp": 1640995200.123,
    "letter": "a",
    "confidence": 0.89,
    "bbox": [100, 150, 50, 40],
    "dot_mask": 1,
    "status": "ok"
  }
}

{
  "event_type": "debug_image",
  "data": {
    "frame_id": 12345,
    "image": numpy.ndarray,
    "overlays": ["aruco", "roi", "dots"]
  }
}
```

## Error Handling

### Error Categories
- **Input Errors**: Invalid frames, missing data
- **Detection Errors**: No marker found, ROI out of bounds
- **Processing Errors**: Memory allocation, OpenCV exceptions
- **Configuration Errors**: Invalid parameters, file I/O issues

### Error Recovery
- **Graceful Degradation**: Continue processing subsequent frames
- **Status Reporting**: Detailed error messages
- **Fallback Mode**: Python-only detection when C++ fails

## Testing Strategy

### Unit Tests
- **Individual Components**: Dot detection, grid mapping, letter recognition
- **Configuration**: Parameter validation, serialization
- **Performance**: Benchmarking, memory profiling

### Integration Tests
- **EventBus**: Message flow, event handling
- **Real Camera**: Live frame processing
- **Calibration**: Interactive calibration routine

### Stress Tests
- **Continuous Processing**: Extended runtime testing
- **Memory Leaks**: Long-running stability
- **Performance**: Sustained throughput measurement

## Deployment Architecture

### File Organization
```
braille_detector/
├── include/
│   └── braille_detector.hpp        # Core class definitions
├── src/
│   ├── braille_detector.cpp       # Main implementation
│   ├── mapping.cpp                 # Letter mapping logic
│   ├── calibration.cpp             # Calibration system
│   └── utils.cpp                   # Helper functions
├── tests/
│   └── test_main.cpp               # Unit test suite
├── examples/
│   ├── braille_listener.py         # Simple integration
│   └── eventbus_integration.py     # Full EventBus service
├── pybind_interface.cpp             # Python bindings
├── CMakeLists.txt                   # Build configuration
└── README.md                        # Documentation
```

### Build Integration
- **CMake**: Automated dependency resolution
- **pybind11**: Seamless Python integration
- **OpenCV**: Full contrib modules support
- **Cross-platform**: Linux ARM64 primary, x86_64 compatible

### Runtime Requirements
- **Dependencies**: OpenCV 4.x, Python 3.7+, nlohmann/json
- **Hardware**: Raspberry Pi 5, PiCamera2, ArUco marker
- **Performance**: 15-20 FPS sustained, <100ms latency

This architecture provides a robust, efficient, and maintainable foundation for real-time Braille detection in the AEye assistive technology ecosystem.
