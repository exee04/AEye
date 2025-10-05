#include "braille_detector.hpp"
#include <opencv2/imgproc.hpp>
#include <opencv2/imgcodecs.hpp>
#include <iostream>
#include <iomanip>
#include <algorithm>

namespace aeye {

// Additional utility functions for visualization and debugging

cv::Mat createROIVisualization(const cv::Mat& roi, const std::vector<cv::Point2f>& dots) {
    cv::Mat vis_roi = roi.clone();
    cv::cvtColor(vis_roi, vis_roi, cv::COLOR_GRAY2BGR);
    
    // Draw detected dots
    for (size_t i = 0; i < dots.size(); i++) {
        cv::circle(vis_roi, dots[i], 4, cv::Scalar(0, 255, 0), -1);
        cv::putText(vis_roi, std::to_string(i + 1), cv::Point(dots[i].x + 8, dots[i].y - 2),
                   cv::FONT_HERSHEY_SIMPLEX, 0.5, cv::Scalar(0, 255, 0), 1);
    }
    
    return vis_roi;
}

cv::Mat createDotMaskVisualization(int dot_mask, const cv::Size& size) {
    cv::Mat vis = cv::Mat::zeros(size, CV_8UC3);
    
    int cell_width = size.width / 2;
    int cell_height = size.height / 3;
    
    // Draw grid
    cv::line(vis, cv::Point(cell_width, 0), cv::Point(cell_width, size.height), cv::Scalar(128), 2);
    cv::line(vis, cv::Point(0, cell_height), cv::Point(size.width, cell_height), cv::Scalar(128), 2);
    cv::line(vis, cv::Point(0, cell_height * 2), cv::Point(size.width, cell_height * 2), cv::Scalar(128), 2);
    
    // Draw dots based on mask
    for (int bit = 0; bit < 6; bit++) {
        if (dot_mask & (1 << bit)) {
            int col = bit / 3;
            int row = bit % 3;
            
            int dot_x = col * cell_width + cell_width / 2;
            int dot_y = row * cell_height + cell_height / 2;
            
            cv::circle(vis, cv::Point(dot_x, dot_y), 20, cv::Scalar(0, 0, 255), -1);
        }
    }
    
    return vis;
}

std::string dotMaskToString(int dot_mask) {
    std::string result = "Binary: ";
    for (int bit = 5; bit >= 0; bit--) {
        result += (dot_mask & (1 << bit)) ? "1" : "0";
    }
    result += " (Hex: 0x" + std::to_string(dot_mask) + ")";
    return result;
}

std::string letterToBits(char letter) {
    auto it = std::find_if(BrailleDetector::BRAILLE_MAP.begin(), BrailleDetector::BRAILLE_MAP.end(),
        [letter](const std::pair<int, char>& p) { return p.second == letter; });
    
    if (it != BrailleDetector::BRAILLE_MAP.end()) {
        return dotMaskToString(it->first);
    }
    return "Unknown letter: " + std::string(1, letter);
}

// Performance measurement utilities
class PerformanceTimer {
public:
    PerformanceTimer(const std::string& name) : name_(name), start_(std::chrono::high_resolution_clock::now()) {}
    
    ~PerformanceTimer() {
        auto end = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start_);
        std::cout << "[Performance] " << name_ << " took " << duration.count() << " μs" << std::endl;
    }

private:
    std::string name_;
    std::chrono::high_resolution_clock::time_point start_;
};

// Configuration validation utilities
bool validateConfig(const Config& config) {
    if (config.min_confidence < 0.0f || config.min_confidence > 1.0f) {
        std::cerr << "[Validation] Invalid min_confidence: " << config.min_confidence << std::endl;
        return false;
    }
    
    if (config.debounce_ms < 0) {
        std::cerr << "[Validation] Invalid debounce_ms: " << config.debounce_ms << std::endl;
        return false;
    }
    
    if (config.stability_frames < 1) {
        std::cerr << "[Validation] Invalid stability_frames: " << config.stability_frames << std::endl;
        return false;
    }
    
    if (config.roi_scaling_factor <= 0.0f) {
        std::cerr << "[Validation] Invalid roi_scaling_factor: " << config.roi_scaling_factor << std::endl;
        return false;
    }
    
    if (config.morphology_kernel_size < 1 || config.morphology_kernel_size % 2 == 0) {
        std::cerr << "[Validation] Invalid morphology_kernel_size: " << config.morphology_kernel_size << std::endl;
        return false;
    }
    
    if (config.adaptive_thresh_block_size < 3 || config.adaptive_thresh_block_size % 2 == 0) {
        std::cerr << "[Validation] Invalid adaptive_thresh_block_size: " << config.adaptive_thresh_block_size << std::endl;
        return false;
    }
    
    return true;
}

// Debug logging utilities
void logDetectionResult(const BrailleResult& result, int frame_id) {
    std::cout << "[Frame " << frame_id << "] Braille Detection:" << std::endl;
    std::cout << "  Letter: " << result.letter << std::endl;
    std::cout << "  Confidence: " << result.confidence << std::endl;
    std::cout << "  Dot Mask: " << dotMaskToString(result.dot_mask) << std::endl;
    std::cout << "  Status: " << result.status << std::endl;
    std::cout << "  BBox: [" << result.bbox.x << ", " << result.bbox.y << ", " 
              << result.bbox.width << ", " << result.bbox.height << "]" << std::endl;
    std::cout << std::endl;
}

void logCalibrationData(const CalibrationData& calibration) {
    std::cout << "[Calibration] Current calibration data:" << std::endl;
    std::cout << "  Dot spacing: " << calibration.dot_spacing_pixels << " pixels" << std::endl;
    std::cout << "  Cell width: " << calibration.cell_width_pixels << " pixels" << std::endl;
    std::cout << "  Cell height: " << calibration.cell_height_pixels << " pixels" << std::endl;
    std::cout << "  Finger tip offset: (" << calibration.fingertip_offset.x 
              << ", " << calibration.fingertip_offset.y << ")" << std::endl;
    std::cout << "  Is calibrated: " << (calibration.is_calibrated ? "Yes" : "No") << std::endl;
}

} // namespace aeye