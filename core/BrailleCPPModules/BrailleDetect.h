#pragma once

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>        // <-- required for py::array_t
#include <opencv2/opencv.hpp>
#include <vector>
#include <deque>
#include <map>

namespace py = pybind11;

struct BrailleCluster {
    std::vector<int> dot_array;
    cv::Rect bbox;
    cv::Point2f center;
    char letter;
};

// Stabilizer class for frame averaging
class BrailleStabilizer {
private:
    std::deque<std::vector<BrailleCluster>> history;
    size_t max_frames;
    float weight_new;
    
public:
    BrailleStabilizer(size_t max_frames = 7, float weight_new = 0.6f);
    std::vector<BrailleCluster> update(const std::vector<BrailleCluster>& clusters);
};

// Original C++ function
std::vector<BrailleCluster> detect_braille(const cv::Mat& frame);

// Wrapper function for Python
std::vector<BrailleCluster> detect_braille_wrapper(py::array_t<uint8_t> input);
