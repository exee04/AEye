#include "FingerDetect.h"         // defines FingerMarker + detect_fingers
#include <pybind11/numpy.h>       // for py::array_t
#include <opencv2/opencv.hpp>     // for cv::Mat
#include <vector>

namespace py = pybind11;

std::vector<FingerMarker> detect_fingers(const cv::Mat& frame) {
    std::vector<FingerMarker> fingers;
    std::vector<int> ids;
    std::vector<std::vector<cv::Point2f>> corners;

    auto dictionary = cv::aruco::getPredefinedDictionary(cv::aruco::DICT_4X4_50);
    cv::aruco::detectMarkers(frame, dictionary, corners, ids);

    for (std::size_t i = 0; i < ids.size(); ++i) {
        cv::Point2f center(0, 0);
        for (auto& pt : corners[i]) {
            center += pt;
        }
        center *= 0.25f;

        fingers.push_back({ids[i], center});
    }

    return fingers;
}

// Wrapper for Python
std::vector<FingerMarker> detect_fingers_wrapper(py::array_t<uint8_t> input) {
    py::buffer_info buf = input.request();
    cv::Mat frame(buf.shape[0], buf.shape[1], CV_8UC3, (uint8_t*)buf.ptr);
    return detect_fingers(frame);
}