import cv2
import numpy as np
import mediapipe as mp
from ultralytics import YOLO

# Load YOLOv8 model
model = YOLO("yolov5xu_ncnn_model")  # Or use yolov8n.pt

# Init MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=2)
mp_draw = mp.solutions.drawing_utils

# OpenCV Webcam Feed
cap = cv2.VideoCapture(0)

while True:
    success, frame = cap.read()
    if not success:
        break

    # Flip and convert color
    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Detect hands
    result = hands.process(rgb)

    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            # Get bounding box around hand
            x_coords = [lm.x * w for lm in hand_landmarks.landmark]
            y_coords = [lm.y * h for lm in hand_landmarks.landmark]
            xmin, xmax = int(min(x_coords)), int(max(x_coords))
            ymin, ymax = int(min(y_coords)), int(max(y_coords))

            # Padding for safety
            pad = 20
            xmin = max(xmin - pad, 0)
            ymin = max(ymin - pad, 0)
            xmax = min(xmax + pad, w)
            ymax = min(ymax + pad, h)

            # Draw hand landmarks
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            # Extract hand region
            hand_img = frame[ymin:ymax, xmin:xmax]

            # Detect objects in hand
            results = model(hand_img, verbose=False)

            for r in results:
                boxes = r.boxes
                for b in boxes:
                    cls = int(b.cls[0])
                    conf = float(b.conf[0])
                    label = model.names[cls]

                    # Convert box to absolute coords (relative to hand region)
                    xyxy = b.xyxy[0].cpu().numpy().astype(int)
                    x1, y1, x2, y2 = xyxy

                    # Draw box on original frame (adjusted for hand region)
                    cv2.rectangle(frame, (xmin + x1, ymin + y1), (xmin + x2, ymin + y2), (0, 255, 0), 2)
                    cv2.putText(frame, f'{label} {conf:.2f}', (xmin + x1, ymin + y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    cv2.imshow("Hand + Object Detection", frame)

    if cv2.waitKey(1) & 0xFF == 27:  # ESC to quit
        break

cap.release()
cv2.destroyAllWindows()
