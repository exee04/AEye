#pragma once

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>        // <-- required for py::array_t
#include <opencv2/opencv.hpp>
#include <vector>

namespace py = pybind11;

struct BrailleCluster {
    std::vector<int> dot_array;
    cv::Rect bbox;
    char letter;
};

// Original C++ function
std::vector<BrailleCluster> detect_braille(const cv::Mat& frame);

// Wrapper function for Python
std::vector<BrailleCluster> detect_braille_wrapper(py::array_t<uint8_t> input);
