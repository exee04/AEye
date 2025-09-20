cmake_minimum_required(VERSION 3.12)
project(BrailleDetection)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(pybind11_DIR "/usr/lib/cmake/pybind11")  # adjust path
find_package(pybind11 REQUIRED)

# Find Python3 (for pybind11)
find_package(Python3 COMPONENTS Development REQUIRED)

# Find pybind11
find_package(pybind11 REQUIRED)

# Find OpenCV
find_package(OpenCV REQUIRED)

# Create pybind11 module
pybind11_add_module(braille_cpp
    BrailleDetect.cpp
    FingerDetect.cpp
    bindings.cpp
)

# Link OpenCV libraries
target_link_libraries(braille_cpp PRIVATE ${OpenCV_LIBS})

# Optional: include directories (helpful if pybind11 or OpenCV headers are non-standard)
target_include_directories(braille_cpp PRIVATE
    ${OpenCV_INCLUDE_DIRS}
    ${Python3_INCLUDE_DIRS}
)



