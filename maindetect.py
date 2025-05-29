from picamera2 import Picamera2
import cv2
import numpy as np
import time
import json

def load_braille_positions():
    try:
        with open('braille_scan_20250520_231629.json', 'r') as f:
            data = json.load(f)
            return data['braille_positions']
    except Exception as e:
        print(f"Error loading braille positions: {e}")
        return []

def draw_braille_positions(frame, marker_center, braille_positions, distance, rot_matrix, tvec, camera_matrix, dist_coeffs):
    # Scale factor based on distance
    scale_factor = 1.0 / (distance + 0.1)
    base_size = 60
    scaled_w = int(base_size * scale_factor)
    scaled_h = int(base_size * scale_factor)
    
    # Ensure minimum size for visibility
    scaled_w = max(scaled_w, 30)
    scaled_h = max(scaled_h, 30)
    
    for braille in braille_positions:
        rel_x, rel_y = braille["relative"]
        label = braille["label"]
        
        # Convert relative position to 3D point (in marker's coordinate system)
        # Convert from mm to meters and invert Y coordinate
        point_3d = np.array([
            rel_x/1000.0,  # Convert mm to meters
            -rel_y/1000.0,  # Invert Y and convert to meters
            0
        ], dtype=np.float32)
        
        # Transform point using rotation matrix
        point_3d_rotated = np.dot(rot_matrix, point_3d)
        
        # Project the transformed point back to 2D
        point_2d, _ = cv2.projectPoints(
            point_3d_rotated.reshape(1, 1, 3),
            np.zeros(3, dtype=np.float32),
            tvec,
            camera_matrix,
            dist_coeffs
        )
        
        # Get the projected point
        abs_x = int(point_2d[0][0][0])
        abs_y = int(point_2d[0][0][1])
        
        # Calculate box corners
        top_left = (int(abs_x - scaled_w/2), int(abs_y - scaled_h/2))
        bottom_right = (int(abs_x + scaled_w/2), int(abs_y + scaled_h/2))
        
        # Draw rectangle
        cv2.rectangle(frame, top_left, bottom_right, (0, 255, 0), 2)
        
        # Adjust text size based on box size
        text_scale = max(0.3, min(0.7, scale_factor))
        cv2.putText(frame, label, 
                   (top_left[0], top_left[1] - 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 
                   text_scale, 
                   (0, 255, 0), 
                   2)

def draw_axes_and_info(frame, marker_corners, camera_matrix, dist_coeffs, marker_size, axis_points, marker_id, braille_positions=None):
    # Define the marker points in 3D space
    marker_points = np.array([
        [-marker_size/2, marker_size/2, 0],
        [marker_size/2, marker_size/2, 0],
        [marker_size/2, -marker_size/2, 0],
        [-marker_size/2, -marker_size/2, 0]
    ], dtype=np.float32)
    
    # Calculate pose
    ret, rvec, tvec = cv2.solvePnP(
        marker_points,
        marker_corners,
        camera_matrix,
        dist_coeffs
    )
    
    # Calculate distance
    distance = np.linalg.norm(tvec)
    
    # Get rotation matrix from rotation vector
    rot_matrix, _ = cv2.Rodrigues(rvec)
    
    # Project the coordinate axes onto the image
    imgpts, jac = cv2.projectPoints(axis_points, rvec, tvec, camera_matrix, dist_coeffs)
    origin = tuple(map(int, imgpts[0].ravel()))
    x_axis = tuple(map(int, imgpts[1].ravel()))
    y_axis = tuple(map(int, imgpts[2].ravel()))
    z_axis = tuple(map(int, imgpts[3].ravel()))
    
    # Draw the coordinate axes with increased thickness
    cv2.line(frame, origin, x_axis, (0, 0, 255), 5)  # X-axis in red
    cv2.line(frame, origin, y_axis, (0, 255, 0), 5)  # Y-axis in green
    cv2.line(frame, origin, z_axis, (255, 0, 0), 5)  # Z-axis in blue
    
    # Add labels for the axes with increased size
    cv2.putText(frame, 'X', x_axis, cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
    cv2.putText(frame, 'Y', y_axis, cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
    cv2.putText(frame, 'Z', z_axis, cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 3)
    
    # Draw a circle at the origin
    cv2.circle(frame, origin, 5, (255, 255, 255), -1)
    
    # Calculate center of the marker
    center = np.mean(marker_corners, axis=0)
    center_point = (int(center[0]), int(center[1]))
    
    if marker_id == 5:
        # Get Euler angles in degrees
        angles = np.degrees(rvec)
        z_angle = abs(angles[2][0])  # Use absolute value of Z rotation angle
        y_angle = angles[1][0]  # Y rotation angle
        
        # Create interaction point in 3D space
        y_offset_3d = 0.06  # 6cm offset in 3D space along Y
        
        # Show interaction point for all angles, using absolute value
        if z_angle > 25 or y_angle < -30:
            # When absolute Z is above 25 degrees or Y is below -30 degrees, use both Y and Z offsets
            z_offset_3d = -0.06  # 6cm offset in 3D space along Z (negative for upward)
            interaction_point_3d = np.array([0, y_offset_3d, z_offset_3d], dtype=np.float32)
        else:
            # When absolute Z is between 0 and 25 degrees and Y is above -30 degrees, only use Y offset
            interaction_point_3d = np.array([0, y_offset_3d, 0], dtype=np.float32)
        
        # Transform the interaction point using the marker's rotation and translation
        interaction_point_3d_rotated = np.dot(rot_matrix, interaction_point_3d)
        interaction_point_3d_translated = interaction_point_3d_rotated + tvec.ravel()
        
        # Project the 3D interaction point to 2D
        interaction_point_2d, _ = cv2.projectPoints(
            interaction_point_3d_translated.reshape(1, 1, 3),
            np.zeros(3, dtype=np.float32),
            np.zeros(3, dtype=np.float32),
            camera_matrix,
            dist_coeffs
        )
        
        interaction_point = (int(interaction_point_2d[0][0][0]), int(interaction_point_2d[0][0][1]))
        
        # Draw the interaction pointer (larger circle)
        cv2.circle(frame, interaction_point, 10, (0, 255, 255), -1)  # Yellow circle for interaction pointer
        
        # Draw a line from marker center to interaction point
        cv2.line(frame, center_point, interaction_point, (0, 255, 255), 2)
    
    # Draw the marker center
    cv2.circle(frame, center_point, 5, (0, 255, 0), -1)
    
    # Display position and rotation information
    cv2.putText(frame, f"Position (m): X:{tvec[0][0]:.2f} Y:{tvec[1][0]:.2f} Z:{tvec[2][0]:.2f}",
              (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, f"Distance: {distance*100:.1f} cm",
              (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    # Display Euler angles
    angles = np.degrees(rvec)
    cv2.putText(frame, f"Rotation (deg): X:{angles[0][0]:.1f} Y:{angles[1][0]:.1f} Z:{angles[2][0]:.1f}",
              (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    # If this is marker ID 1 and we have braille positions, draw them
    if marker_id == 1 and braille_positions:
        draw_braille_positions(frame, center_point, braille_positions, distance, rot_matrix, tvec, camera_matrix, dist_coeffs)
    
    return tvec, distance, angles, center_point

def main():
    # Initialize Picamera2
    picam2 = Picamera2()
    
    # Configure camera - using the same configuration as newnavtest.py
    config = picam2.create_still_configuration(main={"format": "RGB888", "size": (640, 480)})
    picam2.configure(config)
    
    # Start camera
    picam2.start()
    time.sleep(1)  # Camera warm-up
    
    # Load ArUco dictionary - using DICT_4X4_50 like in newnavtest.py
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
    
    # Get camera parameters from picam2
    camera_info = picam2.camera_properties
    width = camera_info['PixelArraySize'][0]
    height = camera_info['PixelArraySize'][1]
    
    # Create camera matrix with proper focal length
    focal_length = max(width, height)
    camera_matrix = np.array([
        [focal_length, 0, width/2],
        [0, focal_length, height/2],
        [0, 0, 1]
    ], dtype=np.float32)
    
    # Initialize distortion coefficients
    dist_coeffs = np.zeros(5, dtype=np.float32)
    
    # Define the marker size in meters (5cm)
    marker_size = 0.05
    
    # Define the coordinate axes points for visualization - increased length
    axis_length = 0.2  # Increased to 20cm for better visibility
    axis_points = np.float32([[0, 0, 0],
                            [axis_length, 0, 0],
                            [0, axis_length, 0],
                            [0, 0, axis_length]])
    
    # Load braille positions
    braille_positions = load_braille_positions()
    
    print("Camera started. Looking for ArUco markers with ID 1 and 5...")
    
    try:
        while True:
            # Capture frame
            frame = picam2.capture_array()
            
            # Convert to grayscale for ArUco detection
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            
            # Detect ArUco markers
            corners, ids, rejected = detector.detectMarkers(gray)
            
            # If markers are detected
            if ids is not None:
                print(f"Detected marker IDs: {ids.flatten()}")
                
                # Draw all detected markers
                cv2.aruco.drawDetectedMarkers(frame, corners, ids)
                
                # Process marker ID 1 (for braille positions)
                if 1 in ids:
                    marker_index = np.where(ids == 1)[0][0]
                    marker_corners = corners[marker_index][0]
                    draw_axes_and_info(frame, marker_corners, camera_matrix, dist_coeffs, 
                                     marker_size, axis_points, 1, braille_positions)
                
                # Process marker ID 5 (for interaction pointer)
                if 5 in ids:
                    marker_index = np.where(ids == 5)[0][0]
                    marker_corners = corners[marker_index][0]
                    draw_axes_and_info(frame, marker_corners, camera_matrix, dist_coeffs, 
                                     marker_size, axis_points, 5)
            else:
                print("No markers detected")
            
            # Display the frame
            cv2.imshow('ArUco Detection', frame)
            
            # Break loop on 'q' press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nStopping camera...")
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        # Clean up
        cv2.destroyAllWindows()
        picam2.stop()

if __name__ == "__main__":
    main()
