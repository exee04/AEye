// BrailleDetect.cpp
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
    cv::cvtColor(frame, gray, cv::COLOR_BGR2GRAY);
    
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
    
    // Setup blob detector with balanced parameters
    cv::SimpleBlobDetector::Params params;
    params.filterByArea = true;
    params.minArea = 5;        // Back to original value
    params.maxArea = 300;      // Back to original value
    params.filterByCircularity = true;
    params.minCircularity = 0.68f;  // Back to original value
    params.filterByConvexity = true;
    params.minConvexity = 0.7f;     // Back to original value
    params.filterByInertia = true;
    params.minInertiaRatio = 0.4f;  // Back to original value
    params.filterByColor = false;   // Disable color filtering for now
    
    cv::Ptr<cv::SimpleBlobDetector> detector = cv::SimpleBlobDetector::create(params);
    
    // Detect blobs
    std::vector<cv::KeyPoint> keypoints;
    detector->detect(opened, keypoints);
    
    // Debug output
    std::cout << "[BrailleDetect] Detected " << keypoints.size() << " keypoints" << std::endl;
    
    if (keypoints.empty()) {
        return clusters;
    }
    
    // Convert keypoints to coordinates
    std::vector<cv::Point2f> coords;
    for (const auto& kp : keypoints) {
        coords.push_back(kp.pt);
    }
    
    int n = coords.size();
    if (n == 0) {
        return clusters;
    }
    
    // Calculate pairwise distances
    std::vector<std::vector<float>> distmat(n, std::vector<float>(n, 0.0f));
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            if (i == j) {
                distmat[i][j] = std::numeric_limits<float>::infinity();
            } else {
                float dx = coords[i].x - coords[j].x;
                float dy = coords[i].y - coords[j].y;
                distmat[i][j] = std::sqrt(dx * dx + dy * dy);
            }
        }
    }
    
    // Find median spacing
    std::vector<float> nearest(n);
    for (int i = 0; i < n; i++) {
        float min_dist = std::numeric_limits<float>::infinity();
        for (int j = 0; j < n; j++) {
            if (i != j && distmat[i][j] < min_dist) {
                min_dist = distmat[i][j];
            }
        }
        nearest[i] = min_dist;
    }
    
    std::sort(nearest.begin(), nearest.end());
    float median_spacing = nearest[n / 2];
    if (median_spacing == 0 || std::isnan(median_spacing)) {
        median_spacing = 10.0f;
    }
    
    float conn_thresh = median_spacing * 1.8f; // Back to original value for better clustering
    
    // Union-Find for clustering
    std::vector<int> parent(n);
    for (int i = 0; i < n; i++) {
        parent[i] = i;
    }
    
    auto uf_find = [&](int x) -> int {
        while (parent[x] != x) {
            parent[x] = parent[parent[x]];
            x = parent[x];
        }
        return x;
    };
    
    auto uf_union = [&](int a, int b) {
        int ra = uf_find(a);
        int rb = uf_find(b);
        if (ra != rb) {
            parent[rb] = ra;
        }
    };
    
    // Union nearby points
    for (int i = 0; i < n; i++) {
        for (int j = i + 1; j < n; j++) {
            if (distmat[i][j] <= conn_thresh) {
                uf_union(i, j);
            }
        }
    }
    
    // Group points by root
    std::map<int, std::vector<int>> groups;
    for (int i = 0; i < n; i++) {
        int root = uf_find(i);
        groups[root].push_back(i);
    }
    
    // Create clusters with better filtering
    for (const auto& group : groups) {
        const std::vector<int>& indices = group.second;
        
        // Skip clusters with too many dots (allow single dots for A, B, C)
        if (indices.size() > 6) {
            continue;
        }
        
        // Calculate bounding box and center
        std::vector<cv::Point2f> cluster_points;
        for (int idx : indices) {
            cluster_points.push_back(coords[idx]);
        }
        
        cv::Rect bbox = cv::boundingRect(cluster_points);
        
        // Filter out clusters that are too small or too large
        if (bbox.width < 8 || bbox.height < 8 || 
            bbox.width > 120 || bbox.height > 120) {
            continue;
        }
        
        // Calculate center
        cv::Point2f center(0, 0);
        for (const auto& pt : cluster_points) {
            center += pt;
        }
        center *= (1.0f / cluster_points.size());
        
        // Create braille cluster
        BrailleCluster cluster;
        cluster.bbox = bbox;
        cluster.center = center;
        cluster.letter = '?'; // Will be determined later
        cluster.dot_array = {0, 0, 0, 0, 0, 0}; // Will be determined later
        
        // Determine dot pattern - simplified approach
        if (indices.size() <= 6) {
            std::vector<int> dot_pattern(6, 0);
            
            // Simple mapping: just fill the first N positions with 1s
            // This is more robust than complex grid mapping
            for (size_t i = 0; i < indices.size() && i < 6; i++) {
                dot_pattern[i] = 1;
            }
            
            cluster.dot_array = dot_pattern;
            
            // Convert dot pattern to letter (simplified mapping)
            std::string dot_string;
            for (int dot : dot_pattern) {
                dot_string += std::to_string(dot);
            }
            
            // Simple letter mapping (you can expand this)
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
        }
        
        clusters.push_back(cluster);
    }
    
    // Debug output
    std::cout << "[BrailleDetect] Created " << clusters.size() << " clusters" << std::endl;
    
    // Apply stabilization to smooth out detection
    return stabilizer.update(clusters);
}

// Wrapper for Python
std::vector<BrailleCluster> detect_braille_wrapper(py::array_t<uint8_t> input) {
    py::buffer_info buf = input.request();
    cv::Mat frame(buf.shape[0], buf.shape[1], CV_8UC3, (uint8_t*)buf.ptr);
    return detect_braille(frame);
}                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   