import cv2
import numpy as np
from picamera2 import Picamera2
import time
import re
import subprocess
import socket
from gpiozero import Button

isActive = False


def connect_to_wifi_nmcli(ssid, password):
    print(f"[??] Trying to connect to: {ssid}")
    result = subprocess.run(
        ["nmcli", "dev", "wifi", "connect", ssid, "password", password],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print(f"[?] Successfully connected to WiFi: {ssid}")
        return True
    else:
        print(f"[?] Failed to connect to WiFi: {ssid}")
        print("Error:", result.stderr)
        return False

def search_for_wifi(stopBtn, picam2):
#     preview_config = picam2.create_preview_configuration(main={"format": 'RGB888', "size": (640, 480)})
#     picam2.configure(preview_config)
    picam2.start()
    time.sleep(2)

    qr_detector = cv2.QRCodeDetector()
    last_data = ""
    
    while True:
        frame = picam2.capture_array()
        data, bbox, _ = qr_detector.detectAndDecode(frame)

        if stopBtn.is_pressed:
            break

        if bbox is not None:
            points = np.int32(bbox).reshape(-1, 2)
            cv2.polylines(frame, [points], True, (0, 255, 0), 2)

            if data:
                cv2.putText(frame, data, (points[0][0], points[0][1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                if data == last_data:
                    print(f"[??] Full QR Data: {data}")
                    match = re.match(r"WIFI:T:(.*?);S:(.*?);P:(.*?);(?:H:(true|false);?)?", data.strip())
                    if match:
                        ssid = match.group(2)
                        password = match.group(3).strip() if match.group(3) else ""
                        print(f"[?] SSID: {ssid}, Password: {password}")
                        connected = connect_to_wifi_nmcli(ssid, password)
                        break
                    else:
                        print("[??] QR format not recognized")
                else:
                    last_data = data
                    print("[??] QR code scanned. Scan again to confirm...")

        cv2.imshow("QR Code Scanner", frame)
        cv2.waitKey(1)
        time.sleep(0.01)

    picam2.stop()
    cv2.destroyAllWindows()
    

def is_connected(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False


