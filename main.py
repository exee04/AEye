import time
from gpiozero import Button, DigitalOutputDevice
import threading
import subprocess
from queue import Queue
import sys

# Initialize vibration module
vibration_module = DigitalOutputDevice(16)

# Initialize all buttons with hold_time for hold detection and bounce_time for debouncing
funcButton1 = Button(17, hold_time=1.0, bounce_time=0.1)  # 1 second hold time, 100ms bounce time
funcButton2 = Button(27, hold_time=1.0, bounce_time=0.1)
funcButton3 = Button(22, hold_time=1.0, bounce_time=0.1)
funcButton4 = Button(23, hold_time=1.0, bounce_time=0.1)
mainBtn = Button(24, hold_time=1.0, bounce_time=0.1)
volUpBtn = Button(6, hold_time=1.0, bounce_time=0.1)
volDownBtn = Button(5, hold_time=1.0, bounce_time=0.1)

# Global mode flags
current_mode = "main"  # Can be "main", "education", or "score"

# Volume and voice settings
current_volume = 100
voice_speed = 150
on_volume_control = False

def vibrate(duration=0.5):
    """Activate vibration module for specified duration"""
    vibration_module.on()
    time.sleep(duration)
    vibration_module.off()

def TTS(text):
    """Text-to-speech function with current volume and speed settings"""
    threading.Thread(target=lambda: subprocess.run([
        'espeak-ng', 
        "-a", str(current_volume),
        "-s", str(voice_speed),
        "-p", "70",
        text
    ])).start()

def update_volume(delta):
    """Update volume with bounds checking"""
    global current_volume
    new_volume = current_volume + delta
    if 0 <= new_volume <= 200:
        current_volume = new_volume
        return True
    return False

def update_voice_speed(delta):
    """Update voice speed with bounds checking"""
    global voice_speed
    new_speed = voice_speed + delta
    if 100 <= new_speed <= 280:
        voice_speed = new_speed
        return True
    return False

def wait_volbutton():
    """Wait for volume button press and return the button number"""
    queue = Queue()
    volUpBtn.when_pressed = queue.put
    volDownBtn.when_pressed = queue.put
    e = queue.get()
    return e.pin.number

def volumeControl():
    """Handle volume and voice speed control"""
    global on_volume_control
    print("Volume control active")
    while True:
        b = wait_volbutton()
        if on_volume_control:
            if b == 6:  # Volume up
                if update_volume(20):
                    TTS("Volume Up")
                    vibrate()
                else:
                    TTS("Max Volume")
                    vibrate()
            elif b == 5:  # Volume down
                if update_volume(-20):
                    TTS("Volume Down")
                    vibrate()
                else:
                    TTS("No Volume")
                    vibrate()
        else:
            if b == 6:  # Speed up
                if update_voice_speed(10):
                    TTS("Increasing Talking Speed")
                    vibrate()
                else:
                    TTS("Max Talking Speed")
                    vibrate()
            elif b == 5:  # Speed down
                if update_voice_speed(-10):
                    TTS("Decreasing Talking Speed")
                    vibrate()
                else:
                    TTS("Minimum Talking Speed")
                    vibrate()
        time.sleep(0.2)

def button_tapped(button_name):
    """Handle button tap with short vibration"""
    print(f"{button_name} tapped!")
    TTS(f"{button_name} tapped!")
    vibrate(0.2)

def educationMode():
    global current_mode
    current_mode = "education"
    print("Education Mode")
    TTS("Education Mode")
    vibrate(0.5)
    
def scoreCheckMode():
    global current_mode
    current_mode = "score"
    print("Score Check Mode")
    TTS("Score Check Mode")
    vibrate(0.5)

def mainFunctions():
    global current_mode
    current_mode = "main"
    print("Main Functions")
    TTS("Main Functions")
    vibrate(0.5)

def secondaryMode():
    global current_mode
    current_mode = "secondary"
    print("Secondary Mode")
    vibrate(0.5)

def wifiMode():
    global current_mode
    current_mode = "wifi"
    print("Wifi Mode")
    vibrate(0.5)

def batteryMode():
    global current_mode
    current_mode = "battery"
    print("Battery Mode")
    vibrate(0.5)

def languageMode():
    global current_mode
    current_mode = "language"
    print("Language Mode")
    vibrate(0.5)

def setup_button_actions():
    """Set up button actions based on current mode"""
    # Set up common button actions
    volUpBtn.when_pressed = lambda: button_tapped("Volume Up")
    volDownBtn.when_pressed = lambda: button_tapped("Volume Down")
    mainBtn.when_pressed = lambda: mainFunctions()

    # Set up mode-specific button actions
    if current_mode == "main":
        funcButton1.when_pressed = lambda: educationMode()
        funcButton2.when_pressed = lambda: scoreCheckMode()
        funcButton3.when_pressed = lambda: button_tapped("Button 3")
        funcButton4.when_pressed = lambda: button_tapped("Button 4")
    elif current_mode == "education":
        funcButton1.when_pressed = lambda: print("Already in Education Mode")
        funcButton2.when_pressed = lambda: scoreCheckMode()
        funcButton3.when_pressed = lambda: button_tapped("None")
        funcButton4.when_pressed = lambda: button_tapped("Button 4")
    elif current_mode == "score":
        funcButton1.when_pressed = lambda: educationMode()
        funcButton2.when_pressed = lambda: print("Already in Score Check Mode")
        funcButton3.when_pressed = lambda: button_tapped("None")
        funcButton4.when_pressed = lambda: button_tapped("Button 4")
    elif current_mode == "secondary":
        funcButton1.when_pressed = lambda: wifiMode()
        funcButton2.when_pressed = lambda: batteryMode()
        funcButton3.when_pressed = lambda: languageMode()
        funcButton4.when_pressed = lambda: mainFunctions()
    elif current_mode == "wifi":
        funcButton1.when_pressed = lambda: print("Already in Wifi Mode")
        funcButton2.when_pressed = lambda: batteryMode()
        funcButton3.when_pressed = lambda: languageMode()
        funcButton4.when_pressed = lambda: mainFunctions()
    elif current_mode == "battery":
        funcButton1.when_pressed = lambda: wifiMode()
        funcButton2.when_pressed = lambda: print("Already in Battery Mode")
        funcButton3.when_pressed = lambda: languageMode()
        funcButton4.when_pressed = lambda: mainFunctions()
    elif current_mode == "language":
        funcButton1.when_pressed = lambda: wifiMode()
        funcButton2.when_pressed = lambda: batteryMode()
        funcButton3.when_pressed = lambda: print("Already in Language Mode")
        funcButton4.when_pressed = lambda: mainFunctions()

def main():
    try:
        # Start volume control in a separate thread
        threading.Thread(target=volumeControl, daemon=True).start()
        
        mainFunctions()  # Start in main mode
        while True:
            setup_button_actions()  # Update button actions based on current mode
            time.sleep(0.1)  # Small delay to prevent CPU overuse
    except KeyboardInterrupt:
        print("\nExiting program...")
        TTS("Exiting program")
    finally:
        # Cleanup
        vibration_module.off()
        sys.exit(0)

if __name__ == "__main__":
    main()
