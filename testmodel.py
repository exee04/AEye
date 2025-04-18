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
    model = YOLO("/home/ky/AEye/AI_Models/best_ncnn_model")  # Replace with your actual model path

    try:
        while True:
            # Capture a frame from the camera
            frame = picam2.capture_array()

            # Convert frame from RGB to BGR if needed (OpenCV expects BGR)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # Run YOLO detection
            results = model(frame)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            # Annotate frame with detections
            annotated_frame = results[0].plot()

            # Show the annotated frame
            cv2.imshow("YOLO Detection", annotated_frame)

            print(f"\n[{timestamp}] Detections:")
            
            # Wait for key press for 1ms, exit on 'q' key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            time.sleep(0.2)  # Small delay to avoid maxing out CPU usage

    except KeyboardInterrupt:
        print("\nStopped by user.")

    finally:
        picam2.close()
        cv2.destroyAllWindows()

startDetection()
