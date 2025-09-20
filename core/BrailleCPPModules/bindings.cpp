#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "BrailleDetect.h"
#include "FingerDetect.h"

namespace py = pybind11;

PYBIND11_MODULE(braille_cpp, m) {
    py::class_<BrailleCluster>(m, "BrailleCluster")
        .def_readwrite("letter", &BrailleCluster::letter)
        .def_readwrite("dot_array", &BrailleCluster::dot_array)
        .def_readwrite("bbox", &BrailleCluster::bbox);

    py::class_<cv::Rect>(m, "Rect")
        .def_readwrite("x", &cv::Rect::x)
        .def_readwrite("y", &cv::Rect::y)
        .def_readwrite("width", &cv::Rect::width)
        .def_readwrite("height", &cv::Rect::height);

    py::class_<FingerMarker>(m, "FingerMarker")
        .def_readwrite("id", &FingerMarker::id)
        .def_readwrite("center", &FingerMarker::center);

    py::class_<cv::Point2f>(m, "Point2f")
        .def_readwrite("x", &cv::Point2f::x)
        .def_readwrite("y", &cv::Point2f::y);

    // ✅ Use wrapper instead of raw cv::Mat function
    m.def("detect_braille", &detect_braille_wrapper);
    m.def("detect_fingers", &detect_fingers_wrapper);
}
