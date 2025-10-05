#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <pybind11/stl_bind.h>

#include "braille_detector.hpp"

namespace py = pybind11;
using namespace aeye;

// Convert cv::Mat to numpy array for Python
py::array_t<uint8_t> matToNumpy(const cv::Mat& mat) {
    std::vector<size_t> shape;
    std::vector<size_t> strides;
    
    if (mat.channels() == 1) {
        shape = {static_cast<size_t>(mat.rows), static_cast<size_t>(mat.cols)};
        strides = {static_cast<size_t>(mat.step[0]), static_cast<size_t>(mat.step[1])};
    } else if (mat.channels() == 3) {
        shape = {static_cast<size_t>(mat.rows), static_cast<size_t>(mat.cols), static_cast<size_t>(mat.channels())};
        strides = {static_cast<size_t>(mat.step[0]), static_cast<size_t>(mat.step[1]), static_cast<size_t>(mat.step[2])};
    }
    
    return py::array_t<uint8_t>(shape, strides, mat.data);
}

// Convert numpy array to cv::Mat
cv::Mat numpyToMat(py::array_t<uint8_t> input) {
    py::buffer_info buf = input.request();
    
    if (buf.ndim == 2) {
        // Grayscale image
        return cv::Mat(static_cast<int>(buf.shape[0]), static_cast<int>(buf.shape[1]), 
                      CV_8UC1, static_cast<uint8_t*>(buf.ptr));
    } else if (buf.ndim == 3 && buf.shape[2] == 3) {
        // Color image (BGR)
        return cv::Mat(static_cast<int>(buf.shape[0]), static_cast<int>(buf.shape[1]), 
                      CV_8UC3, static_cast<uint8_t*>(buf.ptr));
    } else {
        throw std::runtime_error("Unsupported numpy array format");
    }
}

// Python-compatible result structure
struct PythonBrailleResult {
    std::string letter;
    float confidence;
    std::vector<int> bbox;  // [x, y, w, h]
    int dot_mask;
    std::string status;
    py::array_t<uint8_t> debug_image;
};

PythonBrailleResult convertToPythonResult(const BrailleResult& result) {
    PythonBrailleResult py_result;
    py_result.letter = result.letter;
    py_result.confidence = result.confidence;
    py_result.bbox = {result.bbox.x, result.bbox.y, result.bbox.width, result.bbox.height};
    py_result.dot_mask = result.dot_mask;
    py_result.status = result.status;
    
    if (!result.debug_image.empty()) {
        py_result.debug_image = matToNumpy(result.debug_image);
    } else {
        // Return empty array if no debug image
        py_result.debug_image = py::array_t<uint8_t>({0, 0, 3});
    }
    
    return py_result;
}

// Python wrapper class for BrailleDetector
class PythonBrailleDetector {
private:
    std::unique_ptr<BrailleDetector> detector_;
    
public:
    PythonBrailleDetector() : detector_(std::make_unique<BrailleDetector>()) {}
    
    PythonBrailleResult processFrame(int frame_id, double timestamp, py::array_t<uint8_t> frame_array) {
        FrameMsg msg;
        msg.frame_id = frame_id;
        msg.timestamp = timestamp;
        msg.frame = numpyToMat(frame_array);
        
        BrailleResult result = detector_->processFrame(msg);
        return convertToPythonResult(result);
    }
    
    std::string processFrameSimple(py::array_t<uint8_t> frame_array) {
        FrameMsg msg;
        msg.frame_id = 0;
        msg.timestamp = 0.0;
        msg.frame = numpyToMat(frame_array);
        
        BrailleResult result = detector_->processFrame(msg);
        
        if (result.status == "ok") {
            return result.letter;
        }
        return "";
    }
    
    void loadConfig(const std::string& filename) {
        detector_->loadConfig(filename);
    }
    
    void saveConfig(const std::string& filename) {
        detector_->saveConfig(filename);
    }
    
    void startCalibration() {
        detector_->startCalibration();
    }
    
    void endCalibration() {
        detector_->endCalibration();
    }
    
    bool isCalibrated() {
        return detector_->isCalibrated();
    }
    
    void toggleDebug(bool enabled) {
        detector_->toggleDebug(enabled);
    }
    
    void performCalibration(py::array_t<uint8_t> frame_array) {
        cv::Mat frame = numpyToMat(frame_array);
        
        float marker_size;
        cv::Point2f marker_center;
        
        // Create temporary config for marker detection
        Config temp_config = detector_->getConfig();
        auto original_dict = temp_config.dictionary;
        temp_config.dictionary = cv::aruco::DICT_6X6_250;
        
        std::vector<int> marker_ids;
        std::vector<std::vector<cv::Point2f>> marker_corners;
        
        cv::Ptr<cv::aruco::DetectorParameters> parameters = cv::aruco::DetectorParameters::create();
        cv::Ptr<cv::aruco::Dictionary> dictionary = cv::aruco::getPredefinedDictionary(cv::aruco::DICT_6X6_250);
        
        cv::aruco::detectMarkers(frame, dictionary, marker_corners, marker_ids, parameters);
        
        cv::Point2f detected_center(-1, -1);
        for (size_t i = 0; i < marker_ids.size(); i++) {
            if (marker_ids[i] == temp_config.aruco_marker_id) {
                const auto& corners = marker_corners[i];
                cv::Point2f center(0, 0);
                for (const auto& corner : corners) {
                    center += corner;
                }
                detected_center = center * 0.25f;
                break;
            }
        }
        
        if (detected_center.x >= 0 && detected_center.y >= 0) {
            std::cout << "[Calibration] Marker detected at: (" 
                      << detected_center.x << ", " << detected_center.y << ")" << std::endl;
            detector_->updateCalibration(frame, detected_center);
        } else {
            std::cerr << "[Calibration] Marker not detected!" << std::endl;
        }
    }
};

PYBIND11_MODULE(braille_detector_native, m) {
    m.doc() = "Advanced Braille Detection Module with ArUco Finger Tracking";
    
    // Register cv::Point2f as a Python type
    py::class_<cv::Point2f>(m, "Point2f")
        .def(py::init<>())
        .def(py::init<float, float>())
        .def_readwrite("x", &cv::Point2f::x)
        .def_readwrite("y", &cv::Point2f::y);
    
    // Register cv::Rect as a Python type  
    py::class_<cv::Rect>(m, "Rect")
        .def(py::init<>())
        .def(py::init<int, int, int, int>())
        .def_readwrite("x", &cv::Rect::x)
        .def_readwrite("y", &cv::Rect::y)
        .def_readwrite("width", &cv::Rect::width)
        .def_readwrite("height", &cv::Rect::height);
    
    // Expose Config struct
    py::class_<Config>(m, "Config")
        .def(py::init<>())
        .def_readwrite("min_confidence", &Config::min_confidence)
        .def_readwrite("fingertip_offset_ratio", &Config::fingertip_offset_ratio)
        .def_readwrite("debounce_ms", &Config::debounce_ms)
        .def_readwrite("stability_frames", &Config::stability_frames)
        .def_readwrite("debug_mode", &Config::debug_mode)
        .def_readwrite("debug_dir", &Config::debug_dir)
        .def_readwrite("aruco_marker_id", &Config::aruco_marker_id)
        .def_readwrite("roi_scaling_factor", &Config::roi_scaling_factor)
        .def_readwrite("morphology_kernel_size", &Config::morphology_kernel_size)
        .def_readwrite("adaptive_thresh_block_size", &Config::adaptive_thresh_block_size)
        .def_readwrite("adaptive_thresh_c", &Config::adaptive_thresh_c)
        .def_readwrite("calibration_file", &Config::calibration_file);
    
    // Expose BrailleResult
    py::class_<BrailleResult>(m, "BrailleResult")
        .def_readonly("letter", &BrailleResult::letter)
        .def_readonly("confidence", &BrailleResult::confidence)
        .def_readonly("bbox", &BrailleResult::bbox)
        .def_readonly("dot_mask", &BrailleResult::dot_mask)
        .def_readonly("status", &BrailleResult::status);
    
    // Expose FrameMsg  
    py::class_<FrameMsg>(m, "FrameMsg")
        .def(py::init<>())
        .def_readwrite("frame_id", &FrameMsg::frame_id)
        .def_readwrite("timestamp", &FrameMsg::timestamp);
    
    // Python wrapper class
    py::class_<PythonBrailleDetector>(m, "BrailleDetector")
        .def(py::init<>())
        
        // Main processing methods
        .def("process_frame", &PythonBrailleDetector::processFrame,
             py::arg("frame_id"), py::arg("timestamp"), py::arg("frame_array"),
             "Process a frame and return detailed detection results")
             
        .def("detect_letter", &PythonBrailleDetector::processFrameSimple,
             py::arg("frame_array"),
             "Simple letter detection - returns just the detected letter as string")
             
        // Configuration methods
        .def("load_config", &PythonBrailleDetector::loadConfig,
             py::arg("filename"),
             "Load configuration from a JSON file")
             
        .def("save_config", &PythonBrailleDetector::saveConfig,
             py::arg("filename"),
             "Save configuration to a JSON file")
             
        // Calibration methods
        .def("start_calibration", &PythonBrailleDetector::startCalibration,
             "Start calibration mode")
             
        .def("end_calibration", &PythonBrailleDetector::endCalibration,
             "End calibration mode")
             
        .def("is_calibrated", &PythonBrailleDetector::isCalibrated,
             "Check if the detector is calibrated")
             
        .def("perform_calibration", &PythonBrailleDetector::performCalibration,
             py::arg("frame_array"),
             "Perform calibration using the provided frame")
             
        // Debug methods
        .def("toggle_debug", &PythonBrailleDetector::toggleDebug,
             py::arg("enabled"),
             "Enable or disable debug mode");
    
    // Result wrapper for Python
    py::class_<PythonBrailleResult>(m, "PythonBrailleResult")
        .def_readonly("letter", &PythonBrailleResult::letter)
        .def_readonly("confidence", &PythonBrailleResult::confidence)
        .def_readonly("bbox", &PythonBrailleResult::bbox)
        .def_readonly("dot_mask", &PythonBrailleResult::dot_mask)
        .def_readonly("status", &PythonBrailleResult::status)
        .def_readonly("debug_image", &PythonBrailleResult::debug_image);
}
