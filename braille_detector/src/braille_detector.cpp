#include "braille_detector.hpp"
#include <opencv2/imgproc.hpp>
#include <opencv2/imgcodecs.hpp>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

namespace aeye {

BrailleDetector::BrailleDetector() 
    : calibration_mode_(false)
    , debug_enabled_(false)
    , last_publication_letter_mask_(-1)
    , last_publication_time_(std::chrono::system_clock::time_point::min()) {
    // Debug directory will be set when debug mode is enabled
}

BrailleDetector::~BrailleDetector() = default;

BrailleResult BrailleDetector::processFrame(const FrameMsg& msg) {
    BrailleResult result;
    result.status = "error";
    result.confidence = 0.0f;
    result.dot_mask = 0;
    
    if (msg.frame.empty()) {
        result.status = "empty_frame";
        return result;
    }
    
    try {
        // Detect ArUco marker
        float marker_size;
        cv::Point2f marker_center = detectArUcoMarker(msg.frame, marker_size);
        
        if (marker_center.x < 0 || marker_center.y < 0) {
            result.status = "marker_not_found";
            return result;
        }
        
        // Calculate fingertip position
        cv::Point2f fingertip_pos;
        if (!calibration_.is_calibrated) {
            // Use default offset ratio
            std::lock_guard<std::mutex> lock(config_mutex_);
            fingertip_pos = marker_center + cv::Point2f(0, config_.fingertip_offset_ratio * marker_size);
        } else {
            // Use calibrated offset
            std::lock_guard<std::mutex> calib_lock(calibration_mutex_);
            fingertip_pos = marker_center + calibration_.fingertip_offset;
        }
        
        // Handle calibration mode
        if (calibration_mode_) {
            updateCalibration(msg.frame, marker_center);
            result.status = "calibrating";
            return result;
        }
        
        // Extract ROI around fingertip
        cv::Rect roi = extractROI(fingertip_pos, marker_size);
        
        if (roi.x < 0 || roi.y < 0 || roi.x + roi.width >= msg.frame.cols || 
            roi.y + roi.height >= msg.frame.rows) {
            result.status = "roi_out_of_bounds";
            return result;
        }
        
        cv::Mat roi_image = msg.frame(roi);
        
        // Preprocess ROI for dot detection
        cv::Mat processed_roi = preprocessROI(roi_image);
        
        // Detect braille dots
        std::vector<cv::Point2f> dots = detectBrailleDots(processed_roi);
        
        if (dots.empty()) {
            result.status = "no_dots_detected";
            return result;
        }
        
        // Compute dot mask
        int dot_mask = computeDotMask(dots, roi);
        
        // Map to letter
        char letter = mapDotMaskToLetter(dot_mask);
        
        if (letter == '?') {
            result.status = "no_mapping";
            return result;
        }
        
        // Compute confidence
        result.confidence = computeConfidence(dots, BRAILLE_KEYPOINT_COUNT[letter - 'a']);
        
        // Check if we should publish this result
        if (!shouldPublishResult(result)) {
            result.status = "low_confidence";
            return result;
        }
        
        // Fill result
        result.letter = std::string(1, letter);
        result.dot_mask = dot_mask;
        result.bbox = roi;
        result.status = "ok";
        
        // Create debug visualization if enabled
        if (debug_enabled_) {
            result.debug_image = createDebugVisualization(msg.frame, result, marker_center, roi);
            saveDebugFrame(result.debug_image, "frame_" + std::to_string(msg.frame_id));
        }
        
        // Update publication tracking
        last_publication_letter_mask_ = dot_mask;
        last_publication_time_ = std::chrono::system_clock::now();
        
        // Log detection result (verbose logging disabled for production)
        // std::cout << "[BrailleDetector] Letter detected: " << letter << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "[BrailleDetector] Error processing frame: " << e.what() << std::endl;
        result.status = "exception";
    }
    
    return result;
}

cv::Point2f BrailleDetector::detectArUcoMarker(const cv::Mat& frame, float& marker_size) {
    std::vector<int> marker_ids;
    std::vector<std::vector<cv::Point2f>> marker_corners;
    
    cv::Ptr<cv::aruco::DetectorParameters> parameters = cv::aruco::DetectorParameters::create();
    cv::Ptr<cv::aruco::Dictionary> dictionary = cv::aruco::getPredefinedDictionary(cv::aruco::DICT_6X6_250);
    
    cv::aruco::detectMarkers(frame, dictionary, marker_corners, marker_ids, parameters);
    
    cv::Point2f marker_center(-1, -1);
    
    for (size_t i = 0; i < marker_ids.size(); i++) {
        if (marker_ids[i] == config_.aruco_marker_id) {
            // Calculate marker center
            const auto& corners = marker_corners[i];
            cv::Point2f center(0, 0);
            for (const auto& corner : corners) {
                center += corner;
            }
            marker_center = center * 0.25f;
            
            // Calculate marker size (average of width and height)
            float width = cv::norm(corners[0] - corners[1]) + cv::norm(corners[2] - corners[3]);
            float height = cv::norm(corners[0] - corners[3]) + cv::norm(corners[1] - corners[2]);
            marker_size = (width + height) / 4.0f;
            break;
        }
    }
    
    return marker_center;
}

cv::Rect BrailleDetector::extractROI(const cv::Point2f& fingertip_pos, float marker_size) {
    // Calculate ROI size based on marker size
    std::lock_guard<std::mutex> lock(config_mutex_);
    float roi_size = marker_size * config_.roi_scaling_factor;
    
    if (calibration_.is_calibrated) {
        std::lock_guard<std::mutex> calib_lock(calibration_mutex_);
        roi_size = std::max(calibration_.cell_width_pixels, calibration_.cell_height_pixels) * 1.5f;
    }
    
    int half_size = static_cast<int>(roi_size / 2.0f);
    
    cv::Rect roi(
        static_cast<int>(fingertip_pos.x) - half_size,
        static_cast<int>(fingertip_pos.y) - half_size,
        static_cast<int>(roi_size),
        static_cast<int>(roi_size)
    );
    
    return roi;
}

cv::Mat BrailleDetector::preprocessROI(const cv::Mat& roi) {
    cv::Mat gray, clahe_output, bilateral_output, thresh_output;
    
    // Convert to grayscale
    cv::cvtColor(roi, gray, cv::COLOR_BGR2GRAY);
    
    // Apply CLAHE for contrast normalization
    cv::Ptr<cv::CLAHE> clahe = cv::createCLAHE();
    clahe->setClipLimit(2.0);
    clahe->apply(gray, clahe_output);
    
    // Denoise with bilateral filter
    cv::bilateralFilter(clahe_output, bilateral_output, 9, 75, 75);
    
    // Adaptive thresholding
    std::lock_guard<std::mutex> lock(config_mutex_);
    cv::adaptiveThreshold(bilateral_output, thresh_output, 255, 
                         cv::ADAPTIVE_THRESH_GAUSSIAN_C, cv::THRESH_BINARY,
                         config_.adaptive_thresh_block_size, config_.adaptive_thresh_c);
    
    // Morphological operations
    cv::Mat kernel = cv::getStructuringElement(cv::MORPH_ELLIPSE, 
                                              cv::Size(config_.morphology_kernel_size, config_.morphology_kernel_size));
    cv::Mat cleaned;
    cv::morphologyEx(thresh_output, cleaned, cv::MORPH_OPEN, kernel);
    cv::morphologyEx(cleaned, cleaned, cv::MORPH_CLOSE, kernel);
    
    return cleaned;
}

std::vector<cv::Point2f> BrailleDetector::detectBrailleDots(const cv::Mat& processed_roi) {
    // Setup blob detector for braille dots
    cv::SimpleBlobDetector::Params params;
    params.filterByArea = true;
    params.minArea = 8;        // Minimum dot area
    params.maxArea = 150;      // Maximum dot area
    params.filterByCircularity = true;
    params.minCircularity = 0.7f;
    params.filterByConvexity = true;
    params.minConvexity = 0.8f;
    params.filterByInertia = true;
    params.minInertiaRatio = 0.5f;
    params.filterByColor = false;
    
    cv::Ptr<cv::SimpleBlobDetector> detector = cv::SimpleBlobDetector::create(params);
    
    std::vector<cv::KeyPoint> keypoints;
    detector->detect(processed_roi, keypoints);
    
    std::vector<cv::Point2f> dots;
    for (const auto& kp : keypoints) {
        dots.push_back(kp.pt);
    }
    
    return dots;
}

int BrailleDetector::computeDotMask(const std::vector<cv::Point2f>& dots, const cv::Rect& roi) {
    if (dots.empty()) return 0;
    
    // Normalize dot positions to 3x2 grid
    int dot_mask = 0;
    
    // Sort dots by Y coordinate first (rows), then by X coordinate (columns)
    std::vector<cv::Point2f> sorted_dots = dots;
    std::sort(sorted_dots.begin(), sorted_dots.end(), 
        [&roi](const cv::Point2f& a, const cv::Point2f& b) {
            // First sort by row (Y)
            int row_a = std::round(a.y / (roi.height / 3.0f));
            int row_b = std::round(b.y / (roi.height / 3.0f));
            if (row_a != row_b) return row_a < row_b;
            
            // Then sort by column (X) within row
            return a.x < b.x;
        });
    
    // Map each dot to a grid position
    for (const auto& dot : sorted_dots) {
        float relative_x = dot.x / roi.width;
        float relative_y = dot.y / roi.height;
        
        int col = (relative_x < 0.5f) ? 0 : 1;  // Left or right column
        int row = 0;
        if (relative_y < 0.33f) row = 0;        // Top row (dots 1, 4)
        else if (relative_y < 0.67f) row = 1;   // Middle row (dots 2, 5)
        else row = 2;                           // Bottom row (dots 3, 6)
        
        int grid_pos = col * 3 + row;  // Convert to linear index: 0-5
        if (grid_pos >= 0 && grid_pos < 6) {
            dot_mask |= (1 << grid_pos);
        }
    }
    
    return dot_mask;
}

char BrailleDetector::mapDotMaskToLetter(int dot_mask) {
    auto it = BRAILLE_MAP.find(dot_mask);
    if (it != BRAILLE_MAP.end()) {
        return it->second;
    }
    return '?';
}

float BrailleDetector::computeConfidence(const std::vector<cv::Point2f>& dots, int expected_dots) {
    if (expected_dots <= 0) return 0.0f;
    
    int detected_dots = static_cast<int>(dots.size());
    float dot_ratio = static_cast<float>(detected_dots) / static_cast<float>(expected_dots);
    
    // Confidence based on dot count consistency
    float confidence = 1.0f - std::abs(1.0f - dot_ratio);
    
    // Boost confidence if we have the expected number of dots
    if (detected_dots == expected_dots) {
        confidence = std::min(1.0f, confidence + 0.2f);
    }
    
    return std::max(0.0f, confidence);
}

bool BrailleDetector::shouldPublishResult(const BrailleResult& result) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    
    // Check minimum confidence threshold
    if (result.confidence < config_.min_confidence) {
        return false;
    }
    
    // Check debounce timing
    auto now = std::chrono::system_clock::now();
    auto time_since_last = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_publication_time_).count();
    
    if (time_since_last < config_.debounce_ms && 
        last_publication_letter_mask_ == result.dot_mask) {
        return false;  // Debounce - same letter too soon
    }
    
    // Simple stability check - require at least 2 frames with same result
    // For now, we'll just check confidence threshold and debouncing
    return true;
}

cv::Mat BrailleDetector::createDebugVisualization(const cv::Mat& frame, const BrailleResult& result,
                                                 const cv::Point2f& marker_center,
                                                 const cv::Rect& roi) {
    cv::Mat debug_frame = frame.clone();
    
    // Draw marker center
    if (marker_center.x >= 0 && marker_center.y >= 0) {
        cv::circle(debug_frame, marker_center, 10, cv::Scalar(255, 0, 0), 3);
        cv::putText(debug_frame, "ArUco Marker", cv::Point(marker_center.x + 15, marker_center.y),
                   cv::FONT_HERSHEY_SIMPLEX, 0.6, cv::Scalar(255, 0, 0), 2);
    }
    
    // Draw ROI
    if (roi.x >= 0 && roi.y >= 0 && roi.width > 0 && roi.height > 0) {
        cv::rectangle(debug_frame, roi, cv::Scalar(0, 255, 255), 2);
        
        // Draw individual dots in ROI
        cv::Mat roi_image = frame(roi);
        
        // Add letter and confidence text
        std::string info = "Letter: " + result.letter + " (mask: " + std::to_string(result.dot_mask) + 
                          ", conf: " + std::to_string(result.confidence) + ")";
        
        cv::putText(debug_frame, info, cv::Point(roi.x, std::max(15, roi.y - 20)),
                   cv::FONT_HERSHEY_SIMPLEX, 0.7, cv::Scalar(0, 255, 0), 2);
    }
    
    return debug_frame;
}

void BrailleDetector::setConfig(const Config& config) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    config_ = config;
}

Config BrailleDetector::getConfig() const {
    std::lock_guard<std::mutex> lock(config_mutex_);
    return config_;
}

void BrailleDetector::startCalibration() {
    calibration_mode_ = true;
    std::cout << "[BrailleDetector] Calibration started" << std::endl;
}

void BrailleDetector::endCalibration() {
    calibration_mode_ = false;
    if (calibration_.is_calibrated) {
        saveConfig(config_.calibration_file);
        std::cout << "[BrailleDetector] Calibration completed and saved" << std::endl;
    }
}

bool BrailleDetector::isCalibrated() const {
    std::lock_guard<std::mutex> lock(calibration_mutex_);
    return calibration_.is_calibrated;
}

void BrailleDetector::toggleDebug(bool enabled) {
    debug_enabled_ = enabled;
    if (enabled && !config_.debug_dir.empty()) {
        std::filesystem::create_directories(config_.debug_dir);
    }
    std::cout << "[BrailleDetector] Debug mode " << (enabled ? "enabled" : "disabled") << std::endl;
}

void BrailleDetector::saveDebugFrame(const cv::Mat& frame, const std::string& suffix) {
    if (!debug_enabled_ || config_.debug_dir.empty()) return;
    
    auto now = std::chrono::system_clock::now();
    auto timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        now.time_since_epoch()).count();
    
    std::string filename = config_.debug_dir + "/debug_" + suffix + "_" + std::to_string(timestamp) + ".jpg";
    
    try {
        cv::imwrite(filename, frame);
    } catch (const cv::Exception& e) {
        std::cerr << "[BrailleDetector] Failed to save debug frame: " << e.what() << std::endl;
    }
}

void BrailleDetector::initializeCalibration(const cv::Mat& frame, const cv::Point2f& marker_center) {
    std::lock_guard<std::mutex> lock(calibration_mutex_);
    calibration_.fingertip_offset = cv::Point2f(0, -0.35f * 50.0f);  // Default offset
    calibration_.is_calibrated = false;
}

void BrailleDetector::updateCalibration(const cv::Mat& frame, const cv::Point2f& marker_center) {
    std::lock_guard<std::mutex> lock(calibration_mutex_);
    
    // This is a simplified calibration - in a real implementation,
    // you'd collect multiple samples and compute statistics
    calibration_.dot_spacing_pixels = 12.0f;  // Estimated from marker size
    calibration_.cell_width_pixels = 24.0f;
    calibration_.cell_height_pixels = 36.0f;
    calibration_.fingertip_offset = cv::Point2f(0, -0.35f * 50.0f);
    calibration_.is_calibrated = true;
}

// Interactive calibration and validation functions moved to calibration.cpp

} // namespace aeye
