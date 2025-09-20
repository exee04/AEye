#pragma once
#include <opencv2/opencv.hpp>
#include <opencv2/aruco.hpp>
#include <vector>

struct FingerMarker {
    int id;
    cv::Point2f center;
};

// Original C++ function
std::vector<FingerMarker> detect_fingers(const cv::Mat& frame);

// Wrapper function for Python
#include <pybind11/numpy.h>
namespace py = pybind11;
std::vector<FingerMarker> detect_fingers_wrapper(py::array_t<uint8_t> input);