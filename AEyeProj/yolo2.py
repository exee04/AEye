import time
import cv2
from picamera2 import Picamera2
from ultralytics import YOLO

# Set up the camera with reduced resolution
picam2 = Picamera2()
picam2.preview_configuration.main.size = (640, 480)
picam2.preview_configuration.main.format = "RGB888"
picam2.preview_configuration.align()
picam2.configure("preview")
picam2.start()

# Load YOLOv8 model
model = YOLO("yolov5xu_ncnn_model")  # Replace with your actual model path

# Optional: enable/disable logging to a file
log_to_file = False
log_file = open("detection_log.txt", "a") if log_to_file else None

try:
    while True:
        # Capture a frame from the camera
        frame = picam2.capture_array()

        # Run YOLO detection
        results = model(frame)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Annotate frame with detections
        annotated_frame = results[0].plot()

        print(f"\n[{timestamp}] Detections:")

        # Show the annotated frame

        # Exit on 'q' key
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        # Delay between detections
        time.sleep(2)

except KeyboardInterrupt:
    print("\nStopped by user.")

finally:
    if log_to_file:
        log_file.close()
    cv2.destroyAllWindows()
