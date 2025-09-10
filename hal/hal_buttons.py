# hal/hal_buttons.py
import asyncio
import time
from gpiozero import Button, Device

# Detect if running on Pi
def is_raspberry_pi():
    try:
        with open("/proc/cpuinfo", "r") as f:
            return "Raspberry Pi" in f.read()
    except FileNotFoundError:
        return False

if not is_raspberry_pi():
    from gpiozero.pins.mock import MockFactory
    Device.pin_factory = MockFactory()
    print("[ButtonHAL] Using MockFactory (not on Raspberry Pi)")

class ButtonHAL:
    def __init__(self, bus, loop, hold_time=0.5):
        self.bus = bus
        self.loop = loop
        self.hold_time = hold_time
        print("[ButtonHAL] Initializing buttons...")

        # Define all buttons
        self.button1 = Button(17)   # Education / ScoreCheck
        self.button2 = Button(27)   # ObjectDetect / Wi-Fi
        self.button3 = Button(22)   # DistanceCheck / BatteryCheck
        self.button4 = Button(23)   # Mode toggle / PowerOff
        self.volUp   = Button(5)    # Volume Up
        self.volDown = Button(6)    # Volume Down
        self.mainBtn = Button(24)   # Main button (for speech/AI)

        self.buttons = {
            17: self.button1,
            27: self.button2,
            22: self.button3,
            23: self.button4,
            5:  self.volUp,
            6:  self.volDown,
            24: self.mainBtn
        }

        # Track press times
        self.press_times = {}

        # Attach events for all buttons
        for pin, btn in self.buttons.items():
            btn.when_pressed = lambda pin=pin: self.on_press(pin)
            btn.when_released = lambda pin=pin: self.on_release(pin)

        print("[ButtonHAL] Buttons ready:", list(self.buttons.keys()))

    def on_press(self, pin):
        """Record timestamp when button is pressed"""
        self.press_times[pin] = time.time()
        print(f"[ButtonHAL] Button {pin} pressed at {self.press_times[pin]}")

    def on_release(self, pin):
        """Determine if press was a TAP or a HOLD"""
        pressed_at = self.press_times.get(pin, time.time())
        duration = time.time() - pressed_at
        print(f"[ButtonHAL] Button {pin} released after {duration:.2f}s")

        if duration >= self.hold_time:
            print(f"[ButtonHAL] Button {pin} was HELD")
            asyncio.run_coroutine_threadsafe(
                self.bus.publish("button_hold", {"pin": pin, "duration": duration}),
                self.loop
            )
        else:
            print(f"[ButtonHAL] Button {pin} was TAPPED")
            asyncio.run_coroutine_threadsafe(
                self.bus.publish("button_press", {"pin": pin}),
                self.loop
            )
