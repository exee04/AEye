from gpiozero import Button, DigitalOutputDevice
import time
import logging
from threading import Thread

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize vibration module
vibration_module = DigitalOutputDevice(16)

# Initialize all buttons with hold_time for hold detection
funcButton1 = Button(17, hold_time=1.0)  # 1 second hold time
funcButton2 = Button(27, hold_time=1.0)
funcButton3 = Button(22, hold_time=1.0)
funcButton4 = Button(23, hold_time=1.0)
mainBtn = Button(24, hold_time=1.0)
volUpBtn = Button(6, hold_time=1.0)
volDownBtn = Button(5, hold_time=1.0)

# Global variable to track if hold action was triggered
hold_triggered = False

def vibrate(duration=0.5):
    """Activate vibration module for specified duration"""
    vibration_module.on()
    time.sleep(duration)
    vibration_module.off()

def button_tapped(button_name):
    """Handle button tap with short vibration"""
    global hold_triggered
    if not hold_triggered:
        logger.info(f"{button_name} tapped!")
        vibrate(0.2)  # Short vibration for tap

def button_held(button_name):
    """Handle button hold with long vibration"""
    global hold_triggered
    hold_triggered = True
    logger.info(f"{button_name} held!")
    vibrate(1.0)  # Long vibration for hold

def button1_pressed():
    """Special handler for Button 1 press"""
    global hold_triggered
    hold_triggered = False

def button1_released():
    """Special handler for Button 1 release"""
    global hold_triggered
    if not hold_triggered:
        button_tapped("Button 1")

def setup_button_actions():
    """Set up tap and hold actions for all buttons"""
    # Button 1 - special handling for tap and hold
    funcButton1.when_pressed = button1_pressed
    funcButton1.when_released = button1_released
    funcButton1.when_held = lambda: button_held("Button 1")

    # Button 2
    funcButton2.when_pressed = lambda: button_tapped("Button 2")
    funcButton2.when_held = lambda: button_held("Button 2")

    # Button 3
    funcButton3.when_pressed = lambda: button_tapped("Button 3")
    funcButton3.when_held = lambda: button_held("Button 3")

    # Button 4
    funcButton4.when_pressed = lambda: button_tapped("Button 4")
    funcButton4.when_held = lambda: button_held("Button 4")

    # Main Button
    mainBtn.when_pressed = lambda: button_tapped("Main Button")
    mainBtn.when_held = lambda: button_held("Main Button")

    # Volume Up Button
    volUpBtn.when_pressed = lambda: button_tapped("Volume Up")
    volUpBtn.when_held = lambda: button_held("Volume Up")

    # Volume Down Button
    volDownBtn.when_pressed = lambda: button_tapped("Volume Down")
    volDownBtn.when_held = lambda: button_held("Volume Down")

def main():
    logger.info("Starting button test with tap and hold functionality...")
    logger.info("Press any button to test tap, hold for 1 second to test hold action")
    logger.info("Press Ctrl+C to exit")
    
    # Set up button actions
    setup_button_actions()
    
    try:
        # Keep the script running
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Test ended by user")
    finally:
        # Cleanup
        vibration_module.off()
        logger.info("Test completed")

if __name__ == "__main__":
    main()