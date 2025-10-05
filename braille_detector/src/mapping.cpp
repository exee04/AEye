#include "braille_detector.hpp"

namespace aeye {

// Standard uncontracted Braille alphabet mapping (6-dot pattern)
// Each position represents a dot in the 3x2 grid:
// Position 0: dot 1 (top-left)
// Position 1: dot 2 (middle-left) 
// Position 2: dot 3 (bottom-left)
// Position 3: dot 4 (top-right)
// Position 4: dot 5 (middle-right)
// Position 5: dot 6 (bottom-right)

// Static braille mapping definitions
const std::unordered_map<int, char> BrailleDetector::BRAILLE_MAP = {
    {0b000001, 'a'}, {0b000011, 'b'}, {0b001001, 'c'}, {0b011001, 'd'}, {0b010001, 'e'},
    {0b001011, 'f'}, {0b011011, 'g'}, {0b010011, 'h'}, {0b001010, 'i'}, {0b011010, 'j'},
    {0b001101, 'k'}, {0b001111, 'l'}, {0b011101, 'm'}, {0b111101, 'n'}, {0b110101, 'o'},
    {0b011111, 'p'}, {0b111111, 'q'}, {0b110111, 'r'}, {0b011110, 's'}, {0b111110, 't'},
    {0b101101, 'u'}, {0b101111, 'v'}, {0b111011, 'w'}, {0b101101, 'x'}, {0b101111, 'y'},
    {0b111101, 'z'}
};

// Note: In standard literary braille, some letters share patterns:
// U = X = 101101 (dots 1,3,6)
// V = Y = 101111 (dots 1,2,3,6)
// This is correct per braille standards

// Keypoint counts for each letter (number of dots present)
const uint8_t BrailleDetector::BRAILLE_KEYPOINT_COUNT[26] = {
    1,  // A: dot 1
    2,  // B: dots 1,2
    2,  // C: dots 1,4
    3,  // D: dots 1,4,5
    2,  // E: dots 1,5
    3,  // F: dots 1,2,4
    4,  // G: dots 1,2,4,5
    3,  // H: dots 1,2,5
    2,  // I: dots 1,4
    3,  // J: dots 1,4,6
    3,  // K: dots 1,3,4
    4,  // L: dots 1,2,3,4
    4,  // M: dots 1,3,4,5
    5,  // N: dots 1,2,3,4,5
    4,  // O: dots 1,3,4,6
    5,  // P: dots 1,2,3,4,5
    6,  // Q: dots 1,2,3,4,5,6
    5,  // R: dots 1,2,3,4,6
    4,  // S: dots 1,2,4,5
    5,  // T: dots 1,2,3,4,5
    3,  // U: dots 1,3,6
    4,  // V: dots 1,2,3,6
    4,  // W: dots 1,2,4,6
    3,  // X: dots 1,3,6 (same as U)
    4,  // Y: dots 1,2,3,6 (same as V)
    5   // Z: dots 1,3,4,5,6
};

} // namespace aeye
