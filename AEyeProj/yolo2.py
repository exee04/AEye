import time
import cv2
from picamera2 import Picamera2
from ultralytics import YOLO

        

def startDetection():
        # Set up the camera with reduced resolution
        picam2 = Picamera2()
        picam2.preview_configuration.main.size = (640, 480)
        picam2.preview_configuration.main.format = "RGB888"
        picam2.preview_configuration.align()
        picam2.configure("preview")
        picam2.start()

        # Load YOLOv8 model
        model = YOLO("yolov5xu_ncnn_model")  # Replace with your actual model path

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
                        time.sleep(2)

        except KeyboardInterrupt:
                print("\nStopped by user.")

        finally:
                cv2.destroyAllWindows()
