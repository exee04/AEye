import cv2
import numpy as np
from picamera2 import Picamera2
import time
import re
import subprocess

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

def search_for_wifi():
    picam2 = Picamera2()
    picam2.configure(picam2.create_preview_configuration(main={"size": (1920, 1080), "format": "RGB888"}))
    picam2.start()
    time.sleep(2)

    qr_detector = cv2.QRCodeDetector()
    last_data = ""
    ssid = ""
    password = ""

    while True:
        frame = picam2.capture_array()
        data, bbox, _ = qr_detector.detectAndDecode(frame)

        if bbox is not None:
            points = np.int32(bbox).reshape(-1, 2)
            cv2.polylines(frame, [points], True, (0, 255, 0), 2)

            if data:
                cv2.putText(frame, data, (points[0][0], points[0][1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                if data == last_data:
                    print(f"[??] Full QR Data: {data}")

                    match = re.match(r"WIFI:S:(.*?);T:.*?;P:(.*?);;", data)
                    if match:
                        ssid = match.group(1)
                        password = match.group(2)

                        print(f"[?] SSID: {ssid}")
                        print(f"[?] PASSWORD: {password}")

                        picam2.stop()
                        cv2.destroyAllWindows()

                        # Try connecting to WiFi
                        connected = connect_to_wifi_nmcli(ssid, password)
                    
                        return connected
                    else:
                        print("[??] QR format not recognized")

                else:
                    last_data = data
                    print("[??] QR code scanned. Scan again to confirm...")

        cv2.imshow("QR Code Scanner", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    picam2.stop()
    cv2.destroyAllWindows()
    return False

# Run it
if __name__ == "__main__":
    success = search_for_wifi()
    if success:
        print("[??] WiFi connection established!")
    else:
        print("[??] Could not connect to WiFi.")
