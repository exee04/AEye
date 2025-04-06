from picamera2 import Picamera2

picam2 = Picamera2()
camera_info = picam2.sensor_modes

print("Available camera modes and resolutions:\n")
for i, mode in enumerate(camera_info):
    resolution = mode['size']
    print(f"Mode {i}: {resolution}")