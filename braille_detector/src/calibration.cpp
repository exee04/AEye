#include "braille_detector.hpp"
#include <fstream>
#include <nlohmann/json.hpp>
#include <filesystem>
#include <iostream>

using json = nlohmann::json;

namespace aeye {

void BrailleDetector::loadConfig(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "[BrailleDetector] Failed to open config file: " << filename << std::endl;
        return;
    }

    try {
        json config_json;
        file >> config_json;

        {
            std::lock_guard<std::mutex> lock(config_mutex_);
            
            // Load basic config
            if (config_json.contains("min_confidence")) {
                config_.min_confidence = config_json["min_confidence"];
            }
            if (config_json.contains("fingertip_offset_ratio")) {
                config_.fingertip_offset_ratio = config_json["fingertip_offset_ratio"];
            }
            if (config_json.contains("debounce_ms")) {
                config_.debounce_ms = config_json["debounce_ms"];
            }
            if (config_json.contains("stability_frames" )) {
                config_.stability_frames = config_json["stability_frames"];
            }
            if (config_json.contains("debug_mode")) {
                config_.debug_mode = config_json["debug_mode"];
                debug_enabled_ = config_.debug_mode;
            }
            if (config_json.contains("debug_dir")) {
                config_.debug_dir = config_json["debug_dir"];
            }
            if (config_json.contains("aruco_marker_id")) {
                config_.aruco_marker_id = config_json["aruco_marker_id"];
            }
            if (config_json.contains("roi_scaling_factor")) {
                config_.roi_scaling_factor = config_json["roi_scaling_factor"];
            }
            if (config_json.contains("morphology_kernel_size")) {
                config_.morphology_kernel_size = config_json["morphology_kernel_size"];
            }
            if (config_json.contains("adaptive_thresh_block_size")) {
                config_.adaptive_thresh_block_size = config_json["adaptive_thresh_block_size"];
            }
            if (config_json.contains("adaptive_thresh_c")) {
                config_.adaptive_thresh_c = config_json["adaptive_thresh_c"];
            }
        }

        // Load calibration data separately
        if (config_json.contains("calibration")) {
            std::lock_guard<std::mutex> calib_lock(calibration_mutex_);
            
            auto calib_json = config_json["calibration"];
            if (calib_json.contains("dot_spacing_pixels")) {
                calibration_.dot_spacing_pixels = calib_json["dot_spacing_pixels"];
            }
            if (calib_json.contains("cell_width_pixels")) {
                calibration_.cell_width_pixels = calib_json["cell_width_pixels"];
            }
            if (calib_json.contains("cell_height_pixels")) {
                calibration_.cell_height_pixels = calib_json["cell_height_pixels"];
            }
            if (calib_json.contains("fingertip_offset")) {
                auto offset = calib_json["fingertip_offset"];
                calibration_.fingertip_offset.x = offset["x"];
                calibration_.fingertip_offset.y = offset["y"];
            }
            if (calib_json.contains("is_calibrated")) {
                calibration_.is_calibrated = calib_json["is_calibrated"];
            }
        }

        std::cout << "[BrailleDetector] Configuration loaded from: " << filename << std::endl;
        
    } catch (const json::exception& e) {
        std::cerr << "[BrailleDetector] Error parsing config JSON: " << e.what() << std::endl;
    }
}

void BrailleDetector::saveConfig(const std::string& filename) {
    // Create directory if it doesn't exist
    std::filesystem::path file_path(filename);
    std::filesystem::create_directories(file_path.parent_path());

    json config_json;
    
    {
        std::lock_guard<std::mutex> lock(config_mutex_);
        
        config_json["min_confidence"] = config_.min_confidence;
        config_json["fingertip_offset_ratio"] = config_.fingertip_offset_ratio;
        config_json["debounce_ms"] = config_.debounce_ms;
        config_json["stability_frames"] = config_.stability_frames;
        config_json["debug_mode"] = config_.debug_mode;
        config_json["debug_dir"] = config_.debug_dir;
        config_json["aruco_marker_id"] = config_.aruco_marker_id;
        config_json["roi_scaling_factor"] = config_.roi_scaling_factor;
        config_json["morphology_kernel_size"] = config_.morphology_kernel_size;
        config_json["adaptive_thresh_block_size"] = config_.adaptive_thresh_block_size;
        config_json["adaptive_thresh_c"] = config_.adaptive_thresh_c;
    }

    // Save calibration data separately
    {
        std::lock_guard<std::mutex> calib_lock(calibration_mutex_);
        
        json calib_json;
        calib_json["dot_spacing_pixels"] = calibration_.dot_spacing_pixels;
        calib_json["cell_width_pixels"] = calibration_.cell_width_pixels;
        calib_json["cell_height_pixels"] = calibration_.cell_height_pixels;
        
        json offset_json;
        offset_json["x"] = calibration_.fingertip_offset.x;
        offset_json["y"] = calibration_.fingertip_offset.y;
        calib_json["fingertip_offset"] = offset_json;
        
        calib_json["is_calibrated"] = calibration_.is_calibrated;
        
        config_json["calibration"] = calib_json;
    }

    std::ofstream file(filename);
    if (!file.is_open()) {
        std::cerr << "[BrailleDetector] Failed to save config file: " << filename << std::endl;
        return;
    }

    file << config_json.dump(4); // Pretty print with 4-space indent
    std::cout << "[BrailleDetector] Configuration saved to: " << filename << std::endl;
}

void BrailleDetector::performInteractiveCalibration(const cv::Mat& frame) {
    std::cout << "[BrailleDetector] Interactive calibration started..." << std::endl;
    std::cout << "[BrailleDetector] Please place the ArUco marker (ID 4) at a reference braille cell." << std::endl;
    std::cout << "[BrailleDetector] Hold it steady for 5 seconds while we collect calibration data." << std::endl;
    
    float marker_size;
    cv::Point2f marker_center = detectArUcoMarker(frame, marker_size);
    
    if (marker_center.x < 0 || marker_center.y < 0) {
        std::cerr << "[BrailleDetector] Calibration failed: ArUco marker not detected!" << std::endl;
        return;
    }
    
    std::cout << "[BrailleDetector] Marker detected! Computing fingertip offset..." << std::endl;
    
    cv::Point2f estimated_fingertip = marker_center + cv::Point2f(0, config_.fingertip_offset_ratio * marker_size);
    
    // Extract ROI around estimated fingertip
    cv::Rect calibration_roi = extractROI(estimated_fingertip, marker_size);
    
    if (calibration_roi.x < 0 || calibration_roi.y < 0) {
        std::cerr << "[BrailleDetector] Calibration failed: ROI out of bounds!" << std::endl;
        return;
    }
    
    cv::Mat roi_image = frame(calibration_roi);
    
    // Process ROI to find braille dots
    cv::Mat processed_roi = preprocessROI(roi_image);
    std::vector<cv::Point2f> calibration_dots = detectBrailleDots(processed_roi);
    
    if (calibration_dots.empty()) {
        std::cout << "[BrailleDetector] Warning: No braille dots detected during calibration" << std::endl;
        std::cout << "[BrailleDetector] Using default calibration parameters..." << std::endl;
    }
    
    {
        std::lock_guard<std::mutex> calib_lock(calibration_mutex_);
        
        // Compute braille cell dimensions from detected dots
        float avg_dot_spacing = 12.0f;  // Default
        if (calibration_dots.size() >= 2) {
            // Compute average spacing between dots
            float total_spacing = 0.0f;
            int spacing_count = 0;
            
            for (size_t i = 0; i < calibration_dots.size(); i++) {
                for (size_t j = i + 1; j < calibration_dots.size(); j++) {
                    float dist = cv::norm(calibration_dots[i] - calibration_dots[j]);
                    total_spacing += dist;
                    spacing_count++;
                }
            }
            
            if (spacing_count > 0) {
                avg_dot_spacing = total_spacing / spacing_count;
            }
        }
        
        calibration_.dot_spacing_pixels = avg_dot_spacing;
        calibration_.cell_width_pixels = avg_dot_spacing * 2.0f;  // Approximate 2-dot width
        calibration_.cell_height_pixels = avg_dot_spacing * 3.0f; // Approximate 3-dot height
        calibration_.fingertip_offset = cv::Point2f(0, config_.fingertip_offset_ratio * marker_size);
        calibration_.is_calibrated = true;
        
        std::cout << "[BrailleDetector] Calibration completed successfully!" << std::endl;
        std::cout << "[BrailleDetector] Dot spacing: " << avg_dot_spacing << " pixels" << std::endl;
        std::cout << "[BrailleDetector] Cell dimensions: " << calibration_.cell_width_pixels 
                  << " x " << calibration_.cell_height_pixels << " pixels" << std::endl;
        std::cout << "[BrailleDetector] Detected " << calibration_dots.size() << " dots for calibration" << std::endl;
    }
}

void BrailleDetector::validateCalibration() {
    std::lock_guard<std::mutex> calib_lock(calibration_mutex_);
    
    bool valid = true;
    std::vector<std::string> errors;
    
    if (calibration_.dot_spacing_pixels <= 0) {
        errors.push_back("Invalid dot spacing");
        valid = false;
    }
    
    if (calibration_.cell_width_pixels <= 0 || calibration_.cell_height_pixels <= 0) {
        errors.push_back("Invalid cell dimensions");
        valid = false;
    }
    
    if (!valid) {
        std::cerr << "[BrailleDetector] Calibration validation failed:" << std::endl;
        for (const auto& error : errors) {
            std::cerr << "  - " << error << std::endl;
        }
        calibration_.is_calibrated = false;
    } else {
        std::cout << "[BrailleDetector] Calibration validation passed!" << std::endl;
    }
}

} // namespace aeye
