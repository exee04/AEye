#pragma once

#include <opencv2/opencv.hpp>
#include <opencv2/aruco.hpp>
#include <vector>
#include <unordered_map>
#include <string>
#include <atomic>
#include <mutex>
#include <memory>
#include <chrono>
#include <deque>

namespace aeye {

struct FrameMsg {
    int frame_id;
    double timestamp;
    cv::Mat frame;
};

struct BrailleResult {
    std::string letter;
    float confidence;
    cv::Rect bbox;
    int dot_mask;
    std::string status;
    cv::Mat debug_image;
};

struct CalibrationData {
    float dot_spacing_pixels;
    float cell_width_pixels;
    float cell_height_pixels;
    cv::Point2f fingertip_offset;
    bool is_calibrated = false;
};

struct Config {
    // Confidence thresholds
    float min_confidence = 0.8f;
    float fingertip_offset_ratio = -0.35f;
    
    // Timing
    int debounce_ms = 200;
    int stability_frames = 2;
    
    // Debug mode
    bool debug_mode = false;
    std::string debug_dir = "";
    
    // ArUco detection
    cv::aruco::PREDEFINED_DICTIONARY_NAME dictionary = cv::aruco::DICT_6X6_250;
    int aruco_marker_id = 4;
    
    // Image processing parameters
    float roi_scaling_factor = 2.5f;
    int morphology_kernel_size = 3;
    int adaptive_thresh_block_size = 11;
    int adaptive_thresh_c = 2;
    
    // Calibration
    std::string calibration_file = "";
};

class BrailleDetector {
private:

public:
    BrailleDetector();
    ~BrailleDetector();
    
    // Static braille mapping (public for utility functions)
    static const std::unordered_map<int, char> BRAILLE_MAP;
    static const uint8_t BRAILLE_KEYPOINT_COUNT[26];

    // Main interface
    BrailleResult processFrame(const FrameMsg& msg);
    
    // Configuration
    void setConfig(const Config& config);
    Config getConfig() const;
    void loadConfig(const std::string& filename);
    
    // Calibration (public for Python interface)
    void updateCalibration(const cv::Mat& frame, const cv::Point2f& marker_center);
    void saveConfig(const std::string& filename);
    
    // Calibration
    void startCalibration();
    void endCalibration();
    bool isCalibrated() const;
    
    // Debug mode
    void toggleDebug(bool enabled);
    void saveDebugFrame(const cv::Mat& frame, const std::string& suffix);

private:
    Config config_;
    CalibrationData calibration_;
    std::atomic<bool> calibration_mode_;
    std::atomic<bool> debug_enabled_;
    
    // Detection state
    std::deque<BrailleResult> detection_history_;
    std::size_t last_publication_letter_mask_;
    std::chrono::system_clock::time_point last_publication_time_;
    
    // Thread safety
    mutable std::mutex config_mutex_;
    mutable std::mutex calibration_mutex_;
    
    // Internal methods
    cv::Point2f detectArUcoMarker(const cv::Mat& frame, float& marker_size);
    cv::Rect extractROI(const cv::Point2f& fingertip_pos, float marker_size);
    cv::Mat preprocessROI(const cv::Mat& roi);
    std::vector<cv::Point2f> detectBrailleDots(const cv::Mat& processed_roi);
    int computeDotMask(const std::vector<cv::Point2f>& dots, const cv::Rect& roi);
    char mapDotMaskToLetter(int dot_mask);
    float computeConfidence(const std::vector<cv::Point2f>& dots, int expected_dots);
    
    // Helper methods
    cv::Point2f calculateFingertipPosition(const cv::Point2f& marker_center, 
                                         const std::vector<cv::Point2f>& corners);
    bool shouldPublishResult(const BrailleResult& result);
    cv::Mat createDebugVisualization(const cv::Mat& frame, const BrailleResult& result,
                                   const cv::Point2f& marker_center = cv::Point2f(-1, -1),
                                   const cv::Rect& roi = cv::Rect());
    
    // Calibration helpers
    void initializeCalibration(const cv::Mat& frame, const cv::Point2f& marker_center);
    void performInteractiveCalibration(const cv::Mat& frame);
    void validateCalibration();
};

// Static braille mapping definitions moved to mapping.cpp

} // namespace aeye
