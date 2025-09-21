// BrailleDetect_new.cpp - Region-based detection approach
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>       // for py::array_t
#include "BrailleDetect.h"        // your BrailleCluster definition
#include <opencv2/opencv.hpp>
#include <vector>
#include <map>
#include <set>
#include <algorithm>
#include <limits>
#include <cmath>

namespace py = pybind11;

// BrailleStabilizer implementation
BrailleStabilizer::BrailleStabilizer(size_t max_frames, float weight_new) 
    : max_frames(max_frames), weight_new(weight_new) {
    history = std::deque<std::vector<BrailleCluster>>(max_frames);
}

std::vector<BrailleCluster> BrailleStabilizer::update(const std::vector<BrailleCluster>& clusters) {
    std::vector<BrailleCluster> stabilized;
    
    if (history.empty()) {
        for (const auto& c : clusters) {
            stabilized.push_back(c);
        }
        history.push_back(clusters);
        return stabilized;
    }
    
    const auto& prev = history.back();
    if (prev.empty()) {
        history.push_back(clusters);
        return clusters;
    }
    
    // Create cost matrix for Hungarian algorithm (simplified version)
    std::vector<std::vector<float>> cost(prev.size(), std::vector<float>(clusters.size(), 0.0f));
    for (size_t i = 0; i < prev.size(); i++) {
        for (size_t j = 0; j < clusters.size(); j++) {
            float dx = prev[i].center.x - clusters[j].center.x;
            float dy = prev[i].center.y - clusters[j].center.y;
            cost[i][j] = std::sqrt(dx * dx + dy * dy);
        }
    }
    
    // Simple assignment (greedy approach instead of Hungarian)
    std::vector<bool> assigned_prev(prev.size(), false);
    std::vector<bool> assigned_curr(clusters.size(), false);
    
    for (size_t i = 0; i < prev.size(); i++) {
        float min_cost = std::numeric_limits<float>::infinity();
        int best_j = -1;
        
        for (size_t j = 0; j < clusters.size(); j++) {
            if (!assigned_curr[j] && cost[i][j] < min_cost) {
                min_cost = cost[i][j];
                best_j = j;
            }
        }
        
        if (best_j != -1 && min_cost < 50.0f) { // Threshold for matching
            const auto& prev_cluster = prev[i];
            const auto& new_cluster = clusters[best_j];
            
            BrailleCluster stabilized_cluster;
            stabilized_cluster.letter = new_cluster.letter;
            stabilized_cluster.dot_array = new_cluster.dot_array;
            
            // Weighted average of positions
            stabilized_cluster.center.x = prev_cluster.center.x * (1.0f - weight_new) + 
                                        new_cluster.center.x * weight_new;
            stabilized_cluster.center.y = prev_cluster.center.y * (1.0f - weight_new) + 
                                        new_cluster.center.y * weight_new;
            
            // Weighted average of bounding box
            stabilized_cluster.bbox.x = static_cast<int>(prev_cluster.bbox.x * (1.0f - weight_new) + 
                                                        new_cluster.bbox.x * weight_new);
            stabilized_cluster.bbox.y = static_cast<int>(prev_cluster.bbox.y * (1.0f - weight_new) + 
                                                        new_cluster.bbox.y * weight_new);
            stabilized_cluster.bbox.width = static_cast<int>(prev_cluster.bbox.width * (1.0f - weight_new) + 
                                                            new_cluster.bbox.width * weight_new);
            stabilized_cluster.bbox.height = static_cast<int>(prev_cluster.bbox.height * (1.0f - weight_new) + 
                                                             new_cluster.bbox.height * weight_new);
            
            stabilized.push_back(stabilized_cluster);
            assigned_prev[i] = true;
            assigned_curr[best_j] = true;
        }
    }
    
    // Add unmatched clusters as new
    for (size_t j = 0; j < clusters.size(); j++) {
        if (!assigned_curr[j]) {
            stabilized.push_back(clusters[j]);
        }
    }
    
    history.push_back(stabilized);
    return stabilized;
}

// Global stabilizer instance
static BrailleStabilizer stabilizer(7, 0.6f);

std::vector<BrailleCluster> detect_braille(const cv::Mat& frame) {
    std::vector<BrailleCluster> clusters;
    
    if (frame.empty()) {
        return clusters;
    }

    // Convert to grayscale
    cv::Mat gray;
    cv::cvtColor(frame, cv::COLOR_BGR2GRAY);
    
    // Apply Gaussian blur
    cv::Mat blur;
    cv::GaussianBlur(gray, blur, cv::Size(5, 5), 0);
    
    // Adaptive threshold
    cv::Mat thresh;
    cv::adaptiveThreshold(blur, thresh, 255, cv::ADAPTIVE_THRESH_GAUSSIAN_C, cv::THRESH_BINARY_INV, 11, 2);
    
    // Morphological opening
    cv::Mat kernel = cv::getStructuringElement(cv::MORPH_ELLIPSE, cv::Size(3, 3));
    cv::Mat opened;
    cv::morphologyEx(thresh, opened, cv::MORPH_OPEN, kernel, cv::Point(-1, -1), 1);
    
    // Setup blob detector for individual dots
    cv::SimpleBlobDetector::Params params;
    params.filterByArea = true;
    params.minArea = 3;        // Smaller minimum for individual dots
    params.maxArea = 100;      // Smaller maximum for individual dots
    params.filterByCircularity = true;
    params.minCircularity = 0.6f;  // Slightly more lenient
    params.filterByConvexity = true;
    params.minConvexity = 0.6f;    // Slightly more lenient
    params.filterByInertia = true;
    params.minInertiaRatio = 0.3f; // More lenient
    params.filterByColor = false;
    
    cv::Ptr<cv::SimpleBlobDetector> detector = cv::SimpleBlobDetector::create(params);
    
    // Detect individual dots
    std::vector<cv::KeyPoint> keypoints;
    detector->detect(opened, keypoints);
    
    std::cout << "[BrailleDetect] Detected " << keypoints.size() << " individual dots" << std::endl;
    
    if (keypoints.size() < 1) {
        return clusters;
    }
    
    // Convert keypoints to coordinates
    std::vector<cv::Point2f> dots;
    for (const auto& kp : keypoints) {
        dots.push_back(kp.pt);
    }
    
    // Find potential braille letter regions
    // Look for areas where dots could form a 2x3 grid
    float min_letter_width = 15.0f;   // Minimum width for a braille letter
    float max_letter_width = 80.0f;   // Maximum width for a braille letter
    float min_letter_height = 20.0f;  // Minimum height for a braille letter
    float max_letter_height = 60.0f;  // Maximum height for a braille letter
    
    // Group dots by proximity to find potential letter regions
    std::vector<std::vector<cv::Point2f>> letter_regions;
    std::vector<bool> used_dots(dots.size(), false);
    
    for (size_t i = 0; i < dots.size(); i++) {
        if (used_dots[i]) continue;
        
        std::vector<cv::Point2f> region;
        region.push_back(dots[i]);
        used_dots[i] = true;
        
        // Find nearby dots that could be part of the same letter
        for (size_t j = i + 1; j < dots.size(); j++) {
            if (used_dots[j]) continue;
            
            float dist = std::sqrt(std::pow(dots[i].x - dots[j].x, 2) + std::pow(dots[i].y - dots[j].y, 2));
            if (dist <= max_letter_width) {  // Within potential letter width
                region.push_back(dots[j]);
                used_dots[j] = true;
            }
        }
        
        // Check if this region could be a braille letter
        if (region.size() >= 1 && region.size() <= 6) {
            // Calculate bounding box
            float min_x = region[0].x, max_x = region[0].x;
            float min_y = region[0].y, max_y = region[0].y;
            for (const auto& dot : region) {
                min_x = std::min(min_x, dot.x);
                max_x = std::max(max_x, dot.x);
                min_y = std::min(min_y, dot.y);
                max_y = std::max(max_y, dot.y);
            }
            
            float width = max_x - min_x;
            float height = max_y - min_y;
            
            // Check if dimensions are reasonable for a braille letter
            if (width >= min_letter_width && width <= max_letter_width &&
                height >= min_letter_height && height <= max_letter_height) {
                letter_regions.push_back(region);
            }
        }
    }
    
    std::cout << "[BrailleDetect] Found " << letter_regions.size() << " potential letter regions" << std::endl;
    
    // Process each potential letter region
    for (const auto& region : letter_regions) {
        if (region.empty()) continue;
        
        // Calculate bounding box
        float min_x = region[0].x, max_x = region[0].x;
        float min_y = region[0].y, max_y = region[0].y;
        for (const auto& dot : region) {
            min_x = std::min(min_x, dot.x);
            max_x = std::max(max_x, dot.x);
            min_y = std::min(min_y, dot.y);
            max_y = std::max(max_y, dot.y);
        }
        
        cv::Rect bbox(static_cast<int>(min_x - 5), static_cast<int>(min_y - 5),
                     static_cast<int>(max_x - min_x + 10), static_cast<int>(max_y - min_y + 10));
        
        // Calculate center
        cv::Point2f center(0, 0);
        for (const auto& dot : region) {
            center += dot;
        }
        center *= (1.0f / region.size());
        
        // Create braille cluster
        BrailleCluster cluster;
        cluster.bbox = bbox;
        cluster.center = center;
        cluster.letter = '?';
        cluster.dot_array = {0, 0, 0, 0, 0, 0};
        
        // Map dots to 2x3 grid positions
        std::vector<int> dot_pattern(6, 0);
        
        if (region.size() == 1) {
            // Single dot - assume position 0 (dot 1)
            dot_pattern[0] = 1;
        } else {
            // Multiple dots - map to grid positions
            // Sort dots by position
            std::vector<cv::Point2f> sorted_dots = region;
            std::sort(sorted_dots.begin(), sorted_dots.end(), 
                [](const cv::Point2f& a, const cv::Point2f& b) {
                    if (std::abs(a.y - b.y) < 10) {  // Same row
                        return a.x < b.x;
                    }
                    return a.y < b.y;  // Different rows
                });
            
            // Map to 2x3 grid: [1,4] [2,5]
            //                 [3,6]
            float region_width = max_x - min_x;
            float region_height = max_y - min_y;
            
            for (const auto& dot : sorted_dots) {
                float rel_x = (dot.x - min_x) / std::max(region_width, 1.0f);
                float rel_y = (dot.y - min_y) / std::max(region_height, 1.0f);
                
                int col = (rel_x < 0.5f) ? 0 : 1;  // Left or right column
                int row = (rel_y < 0.33f) ? 0 : (rel_y < 0.67f) ? 1 : 2;  // Top, middle, or bottom row
                
                int grid_pos = col * 3 + row;  // Convert to linear index
                if (grid_pos >= 0 && grid_pos < 6) {
                    dot_pattern[grid_pos] = 1;
                }
            }
        }
        
        cluster.dot_array = dot_pattern;
        
        // Convert dot pattern to letter
        std::string dot_string;
        for (int dot : dot_pattern) {
            dot_string += std::to_string(dot);
        }
        
        // Map to letters
        if (dot_string == "100000") cluster.letter = 'A';
        else if (dot_string == "110000") cluster.letter = 'B';
        else if (dot_string == "100100") cluster.letter = 'C';
        else if (dot_string == "100110") cluster.letter = 'D';
        else if (dot_string == "100010") cluster.letter = 'E';
        else if (dot_string == "110100") cluster.letter = 'F';
        else if (dot_string == "110110") cluster.letter = 'G';
        else if (dot_string == "110010") cluster.letter = 'H';
        else if (dot_string == "010100") cluster.letter = 'I';
        else if (dot_string == "010110") cluster.letter = 'J';
        else if (dot_string == "101000") cluster.letter = 'K';
        else if (dot_string == "111000") cluster.letter = 'L';
        else if (dot_string == "101100") cluster.letter = 'M';
        else if (dot_string == "101110") cluster.letter = 'N';
        else if (dot_string == "101010") cluster.letter = 'O';
        else if (dot_string == "111100") cluster.letter = 'P';
        else if (dot_string == "111110") cluster.letter = 'Q';
        else if (dot_string == "111010") cluster.letter = 'R';
        else if (dot_string == "011100") cluster.letter = 'S';
        else if (dot_string == "011110") cluster.letter = 'T';
        else if (dot_string == "101001") cluster.letter = 'U';
        else if (dot_string == "111001") cluster.letter = 'V';
        else if (dot_string == "010111") cluster.letter = 'W';
        else if (dot_string == "101101") cluster.letter = 'X';
        else if (dot_string == "101111") cluster.letter = 'Y';
        else if (dot_string == "101011") cluster.letter = 'Z';
        else cluster.letter = '?';
        
        clusters.push_back(cluster);
    }
    
    std::cout << "[BrailleDetect] Created " << clusters.size() << " braille letters" << std::endl;
    
    // Apply stabilization to smooth out detection
    return stabilizer.update(clusters);
}

// Wrapper for Python
std::vector<BrailleCluster> detect_braille_wrapper(py::array_t<uint8_t> input) {
    py::buffer_info buf = input.request();
    cv::Mat frame(buf.shape[0], buf.shape[1], CV_8UC3, (uint8_t*)buf.ptr);
    return detect_braille(frame);
}
