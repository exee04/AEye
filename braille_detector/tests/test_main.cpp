#include <iostream>
#include <opencv2/opencv.hpp>
#include "../include/braille_detector.hpp"

using namespace aeye;

void testBrailleMapping() {
    std::cout << "Testing Braille letter mapping..." << std::endl;
    
    // Test a few known mappings
    char test_cases[] = {'a', 'b', 'c', 'd', 'e', 'z'};
    int expected_masks[] = {0b000001, 0b000011, 0b001001, 0b011001, 0b010001, 0b111101};
    
    for (int i = 0; i < 6; i++) {
        char letter = BrailleDetector::BRAILLE_MAP.at(expected_masks[i]);
        if (letter == test_cases[i]) {
            std::cout << "✓ Letter " << test_cases[i] << " correctly mapped" << std::endl;
        } else {
            std::cout << "✗ Letter " << test_cases[i] << " mapping failed: got " << letter << std::endl;
        }
    }
}

void testDotMaskComputation() {
    std::cout << "\nTesting dot mask computation..." << std::endl;
    
    BrailleDetector detector;
    
    // Create mock dots for letter 'a' (dot 1 only)
    std::vector<cv::Point2f> dots_a = {
        cv::Point2f(10, 10)  // Should map to position 0 (dot 1)
    };
    
    cv::Rect roi(0, 0, 40, 30);  // Mock ROI
    int mask = detector.computeDotMask(dots_a, roi);
    
    if (mask == 0b000001) {  // Expected for letter 'a'
        std::cout << "✓ Dot mask computation for letter 'a' correct: " << mask << std::endl;
    } else {
        std::cout << "✗ Dot mask computation failed: got " << mask << ", expected 1" << std::endl;
    }
}

void testConfidenceComputation() {
    std::cout << "\nTesting confidence computation..." << std::endl;
    
    BrailleDetector detector;
    
    // Test perfect match
    std::vector<cv::Point2f> dots_perfect = {
        cv::Point2f(10, 10), cv::Point2f(20, 15)  // 2 dots for letter 'b'
    };
    
    float conf_perfect = detector.computeConfidence(dots_perfect, 2);
    std::cout << "Perfect match confidence: " << conf_perfect << std::endl;
    
    // Test over-detection
    std::vector<cv::Point2f> dots_over = {
        cv::Point2f(10, 10), cv::Point2f(20, 15), cv::Point2f(30, 20), cv::Point2f(40, 25)
    };
    
    float conf_over = detector.computeConfidence(dots_over, 2);
    std::cout << "Over-detection confidence: " << conf_over << std::endl;
    
    // Test under-detection
    std::vector<cv::Point2f> dots_under = {
        cv::Point2f(10, 10)  // 1 dot when expecting 2
    };
    
    float conf_under = detector.computeConfidence(dots_under, 2);
    std::cout << "Under-detection confidence: " << conf_under << std::endl;
}

cv::Mat createMockFrame() {
    cv::Mat frame = cv::Mat::zeros(480, 640, CV_8UC3);
    
    // Add some background texture
    cv::randu(frame, cv::Scalar(50, 50, 50), cv::Scalar(200, 200, 200));
    
    // Add mock ArUco marker (simple square)
    cv::rectangle(frame, cv::Rect(100, 100, 50, 50), cv::Scalar(255, 255, 255), -1);
    cv::rectangle(frame, cv::Rect(100, 100, 50, 50), cv::Scalar(0, 0, 0), 3);
    
    // Add mock braille dots near marker
    cv::circle(frame, cv::Point(120, 180), 3, cv::Scalar(0, 0, 0), -1);  // Dot 1
    
    return frame;
}

void testFrameProcessing() {
    std::cout << "\nTesting frame processing..." << std::endl;
    
    BrailleDetector detector;
    detector.toggleDebug(true);  // Enable debug for visualization
    
    auto mock_frame = createMockFrame();
    
    FrameMsg msg;
    msg.frame_id = 0;
    msg.timestamp = 0.0;
    msg.frame = mock_frame;
    
    BrailleResult result = detector.processFrame(msg);
    
    std::cout << "Frame processing result:" << std::endl;
    std::cout << "  Status: " << result.status << std::endl;
    std::cout << "  Letter: " << result.letter << std::endl;
    std::cout << "  Confidence: " << result.confidence << std::endl;
    std::cout << "  Dot mask: " << result.dot_mask << std::endl;
}

void testConfiguration() {
    std::cout << "\nTesting configuration..." << std::endl;
    
    BrailleDetector detector;
    
    Config config = detector.getConfig();
    std::cout << "Default config:" << std::endl;
    std::cout << "  Min confidence: " << config.min_confidence << std::endl;
    std::cout << "  Debug mode: " << config.debug_mode << std::endl;
    std::cout << "  ArUco marker ID: " << config.aruco_marker_id << std::endl;
    
    // Test config modification
    config.min_confidence = 0.9f;
    config.debug_mode = true;
    detector.setConfig(config);
    
    Config new_config = detector.getConfig();
    if (new_config.min_confidence == 0.9f && new_config.debug_mode == true) {
        std::cout << "✓ Configuration modification successful" << std::endl;
    } else {
        std::cout << "✗ Configuration modification failed" << std::endl;
    }
}

void testCalibration() {
    std::cout << "\nTesting calibration..." << std::endl;
    
    BrailleDetector detector;
    
    if (!detector.isCalibrated()) {
        std::cout << "✓ Initial state: not calibrated" << std::endl;
    }
    
    detector.startCalibration();
    
    auto mock_frame = createMockFrame();
    
    FrameMsg msg;
    msg.frame_id = 0;
    msg.timestamp = 0.0;
    msg.frame = mock_frame;
    
    detector.updateCalibration(mock_frame, cv::Point2f(125, 125));
    
    detector.endCalibration();
    
    if (detector.isCalibrated()) {
        std::cout << "✓ Calibration successful" << std::endl;
    } else {
        std::cout << "✗ Calibration failed" << std::endl;
    }
}

int main() {
    std::cout << "=== BrailleDetector Test Suite ===" << std::endl;
    
    try {
        testBrailleMapping();
        testDotMaskComputation();
        testConfidenceComputation();
        testFrameProcessing();
        testConfiguration();
        testCalibration();
        
        std::cout << "\n=== All Tests Completed ===" << std::endl;
        return 0;
        
    } catch (const std::exception& e) {
        std::cerr << "Test failed with exception: " << e.what() << std::endl;
        return 1;
    }
}
