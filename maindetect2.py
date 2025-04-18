import cv2
import json
import numpy as np
from ultralytics import YOLO
import mediapipe as mp
from picamera2 import Picamera2
import time

# Load model
model = YOLO("/home/ky/AEye/AI_Models/best_ncnn_model")

# Hand Tracker
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1)

# ArUco setup
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()
detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

# Camera setup (Picamera2)
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"format":"RGB888","size":(640,480)}))
picam2.start()

# States
scanned_labels = set()  # Keep track of scanned labels
scanned_boxes = []      # Keep track of scanned boxes for drawing

pause_time = 2  # Pause time after detecting a Braille letter

# Scanning phase: Wait for user to press 's' when ready
print("Place ArUco marker on paper and press 's' to start scanning.")

while True:
    frame = picam2.capture_array()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect ArUco marker
    corners, ids, _ = detector.detectMarkers(gray)
    if ids is not None:
        frame = cv2.aruco.drawDetectedMarkers(frame, corners, ids)

    # Scanning phase: Wait for the 's' key to start
    cv2.imshow("Scan Phase - Place ArUco Marker", frame)
    if cv2.waitKey(1) & 0xFF == ord('s'):
        print("Scanning Braille labels...")
        yolo_res = model(frame)[0]
        boxes = []
        for b in yolo_res.boxes:
            conf = float(b.conf[0])
            if conf >= 0.95:  # High-confidence detection
                x1, y1, x2, y2 = map(int, b.xyxy[0])
                label = model.names[int(b.cls[0])]
                boxes.append(((x1, y1, x2, y2), label))
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

        # Save scanned Braille locations
        with open("braille_map.json", "w") as f:
            json.dump(boxes, f)
        print(f"Scanned {len(boxes)} Braille labels.")
        break  # After scanning, proceed to the next phase

# Detection phase: Now continuously track hand and detect the scanned labels
while True:
    frame = picam2.capture_array()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect ArUco marker again (for homography)
    corners, ids, _ = detector.detectMarkers(gray)
    if ids is not None:
        frame = cv2.aruco.drawDetectedMarkers(frame, corners, ids)

    # Load saved scanned Braille data (boxes and labels)
    with open("braille_map.json", "r") as f:
        scanned_boxes = json.load(f)

    # Draw previously scanned labels & boxes in real-time
    for (x1, y1, x2, y2), label in scanned_boxes:
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)  # Green box for scanned labels
        cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    # YOLO detection
    yolo_res = model(frame)[0]
    boxes = []
    for b in yolo_res.boxes:
        conf = float(b.conf[0])
        if conf >= 0.95:
            x1, y1, x2, y2 = map(int, b.xyxy[0])
            label = model.names[int(b.cls[0])]
            boxes.append(((x1, y1, x2, y2), label))

    # Hand tracking
    hand_res = hands.process(frame)
    if hand_res.multi_hand_landmarks:
        for hl in hand_res.multi_hand_landmarks:
            h, w, _ = frame.shape
            pt = hl.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
            fx, fy = int(pt.x*w), int(pt.y*h)
            cv2.circle(frame, (fx, fy), 10, (0, 255, 0), -1)

            # Check if the finger is on any scanned label
            for (x1, y1, x2, y2), label in scanned_boxes:
                if x1 <= fx <= x2 and y1 <= fy <= y2:
                    print(f"📍 Pointing at: {label}")
                    cv2.putText(frame, f"Pointing at: {label}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
                    time.sleep(pause_time)  # Pause after detection

    # Show the result (optional for debugging)
    cv2.imshow("Detection Mode", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()
