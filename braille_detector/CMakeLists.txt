cmake_minimum_required(VERSION 3.12)
project(BrailleDetector)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Set default build type to Release if not specified
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Enable useful compiler flags for optimization
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG")

# Find required packages
set(OpenCV_DIR "/usr/lib/aarch64-linux-gnu/cmake/opencv4")
find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs calib3d aruco)
find_package(pybind11 REQUIRED)
find_package(Python3 COMPONENTS Development REQUIRED)

# Find nlohmann/json library
find_package(nlohmann_json REQUIRED)

# Create pybind11 module
pybind11_add_module(braille_detector_native
    pybind_interface.cpp
    src/braille_detector.cpp
    src/mapping.cpp
    src/calibration.cpp
    src/utils.cpp
)

# Set output properties
set_target_properties(braille_detector_native PROPERTIES
    OUTPUT_NAME braille_detector_native
    SUFFIX .so
)

# Link libraries
target_link_libraries(braille_detector_native PRIVATE 
    ${OpenCV_LIBS}
    nlohmann_json::nlohmann_json
)

# Include directories
target_include_directories(braille_detector_native PRIVATE
    include
    ${OpenCV_INCLUDE_DIRS}
    ${Python3_INCLUDE_DIRS}
)

# Compiler-specific options
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    target_compile_options(braille_detector_native PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
    target_compile_options(braille_detector_native PRIVATE -Wall -Wextra -Wpedantic)
endif()

# Installation rules
install(TARGETS braille_detector_native 
        LIBRARY DESTINATION lib/python${Python3_VERSION_MAJOR}.${Python3_VERSION_MINOR}/site-packages)

# Set RPATH for runtime
set_target_properties(braille_detector_native PROPERTIES
    BUILD_RPATH "${OpenCV_LIB_DIRS}"
    INSTALL_RPATH_USE_LINK_PATH TRUE
)

# Print configuration summary
message(STATUS "BrailleDetector Configuration:")
message(STATUS "  CMAKE_BUILD_TYPE: ${CMAKE_BUILD_TYPE}")
message(STATUS "  OpenCV_VERSION: ${OpenCV_VERSION}")
message(STATUS "  OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message(STATUS "  OpenCV_LIBS: ${OpenCV_LIBS}")
message(STATUS "  Python3_VERSION: ${Python3_VERSION}")
message(STATUS "  Python3_INCLUDE_DIRS: ${Python3_INCLUDE_DIRS}")
message(STATUS "  pybind11_VERSION: ${pybind11_VERSION}")

# Test executable removed - requires public access to private methods
# Use Python tests instead: python3 -c "import braille_detector_native as bd; print('Module loaded successfully')"
