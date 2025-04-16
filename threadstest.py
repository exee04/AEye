from gpiozero import Button
from signal import pause
import threading
import time
import RPi.GPIO as GPIO

GPIO.cleanup

# Button on GPIO pin 2
stop_button = Button(17)

# Use an Event to signal the thread to stop
stop_event = threading.Event()

def my_thread():
    while not stop_event.is_set():
        print("Thread running...")
        time.sleep(0.1)
    print("Thread stopped!")

# Function to stop the thread when button is pressed
def stop_thread():
    print("Button pressed! Stopping thread...")
    stop_event.set()

# Set up button press handler
stop_button.when_pressed = stop_thread

# Start the thread
t = threading.Thread(target=my_thread)
t.start()

# Wait for button press events
pause()
