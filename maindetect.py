from ultralytics import YOLO
import mediapipe as mp
from picamera2 import Picamera2
import time
import os
model = YOLO("/home/ky/AEye/AI_Models/best_ncnn_model")

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1)

import cv2

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"format": "RGB888", "size": (640, 480)}))
picam2.start()
time.sleep(1)  # allow camera to warm up

while True:
    frame = picam2.capture_array()
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Run YOLOv8
    results = model(img_rgb)[0]

    # Run MediaPipe
    hand_results = hands.process(img_rgb)

    # Run MediaPipe
    hand_results = hands.process(img_rgb)

    # Draw and Analyze
    if hand_results.multi_hand_landmarks:
        for hand_landmarks in hand_results.multi_hand_landmarks:
            index_finger = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
            h, w, _ = frame.shape
            finger_x, finger_y = int(index_finger.x * w), int(index_finger.y * h)

            # Draw fingertip
            cv2.circle(frame, (finger_x, finger_y), 10, (0, 255, 0), -1)

            for box in results.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                confidence = box.conf[0]  # Confidence score for the box
                label = model.names[int(box.cls[0])]

                # Only proceed if confidence is 95% or higher
                if confidence >= 0.90:
                    print(f"Detected with high confidence ({confidence*100:.2f}%): {label}")
        
                    # Draw the bounding box and label (only if confident enough)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                    cv2.putText(frame, f"Pointing: {label}", (x1, y2 + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                    # Check if the finger is inside this box
                    if x1 <= finger_x <= x2 and y1 <= finger_y <= y2:
                        print(f"\n🧠 You are pointing at Braille letter: {label}")
                        os.system(f'espeak-ng "You are pointing at letter {label}"')

                        # Pause until user presses a key
                        print("🔴 Paused. Press ENTER to continue...")
                        input()

            

    cv2.imshow("Camera Feed", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    time.sleep(0.03)

cv2.destroyAllWindows()