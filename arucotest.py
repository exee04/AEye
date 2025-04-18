import cv2
import numpy as np
from picamera2 import Picamera2
import time
from ultralytics import YOLO

# Initialize Picamera2
picam2 = Picamera2()
picam2.preview_configuration.main.size = (1920, 1080)  # Set preview resolution
picam2.configure(picam2.preview_configuration)
picam2.start()
time.sleep(2)  # Allow camera to warm up

# Load YOLOv8 model (replace with the path to your trained Braille detection model)
braille_model = YOLO('/home/ky/AEye/AI_Models/best_ncnn_model')  # Ensure this is the correct path to your model

# Load predefined ArUco dictionary
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
parameters = cv2.aruco.DetectorParameters()  # Create detector parameters for marker detection

desired_ids = [0, 1, 2, 3]

# Function to detect ArUco markers in the frame
def detect_aruco_markers(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = cv2.aruco.GridBoard(gray, aruco_dict, parameters=parameters)
    
    if ids is not None and len(ids) > 0:
        cv2.aruco.drawDetectedMarkers(frame, corners, ids)
        found_ids = [id[0] for id in ids]
        matched_ids = [id for id in found_ids if id in desired_ids]
        
        if len(set(matched_ids)) >= 4:
            return True, frame, corners, ids
    return False, frame, None, None

# Function to calculate the center of a corner
def get_center(corner):
    return np.mean(corner[0], axis=0)

# Perspective transformation to get coordinates relative to the markers
def transform_braille_coordinates(x_center, y_center, matrix):
    point = np.array([x_center, y_center, 1]).reshape(1, 3)
    point_transformed = np.linalg.inv(matrix).dot(point.T)
    return point_transformed[0][0], point_transformed[1][0]

# Main loop to capture the image and process Braille detection
def capture_and_process_image():
    print("Looking for 4 unique ArUco markers with IDs 0, 1, 2, 3...")
    
    while True:
        # Capture frame from the camera
        frame = picam2.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

        detected, frame_with_markers, corners, ids = detect_aruco_markers(frame)

        if detected:
            print("Detected 4 ArUco markers!")

            # Get the coordinates of the markers
            id_to_corner = {id[0]: corner for corner, id in zip(corners, ids)}

            if all(id in id_to_corner for id in desired_ids):
                pts_src = np.array([
                    get_center(id_to_corner[0]),  # top-left
                    get_center(id_to_corner[1]),  # top-right
                    get_center(id_to_corner[2]),  # bottom-right
                    get_center(id_to_corner[3])   # bottom-left
                ], dtype="float32")

                # Define the destination rectangle for perspective transformation
                width, height = 800, 800
                buffer_percentage = 0.5
                buffer_width = int(width * (1 + buffer_percentage))
                buffer_height = int(height * (1 + buffer_percentage))

                pts_dst = np.array([
                    [0, 0],
                    [buffer_width - 1, 0],
                    [buffer_width - 1, buffer_height - 1],
                    [0, buffer_height - 1]
                ], dtype="float32")

                # Perspective transform matrix
                matrix = cv2.getPerspectiveTransform(pts_src, pts_dst)
                warped = cv2.warpPerspective(frame_with_markers, matrix, (buffer_width, buffer_height))

                # Save the final cropped image
                cv2.imwrite("cropped_flat_image.jpg", warped)
                print("Flat cropped image saved as 'cropped_flat_image.jpg'")

                # Run YOLOv8 to detect Braille inside the markers
                results = braille_model(warped)  # Apply YOLOv8 model

                # Extract Braille coordinates and transform them relative to the markers
                boxes = results.xywh[0]  # First image in batch (if batch size > 1)
                with open('braille_coordinates.txt', 'w') as f:
                    for box in boxes:
                        x_center, y_center, width, height, confidence, class_id = box
                        relative_x, relative_y = transform_braille_coordinates(x_center, y_center, matrix)
                        f.write(f'Braille ID: {class_id} - Coordinates: ({relative_x}, {relative_y})\n')
                        print(f'Relative position of Braille: ({relative_x}, {relative_y})')

                break  # Exit loop after processing

        # Show live view
        cv2.imshow('Aruco Detection', frame_with_markers)

        # Press 'q' to quit manually
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Quit requested. Exiting.")
            break

    picam2.stop()
    cv2.destroyAllWindows()

# Run the capture and process function
capture_and_process_image()
