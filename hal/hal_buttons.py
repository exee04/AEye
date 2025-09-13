# hal/hal_buttons.py
import asyncio
import time
import threading
from gpiozero import Button, Device

# Detect if running on Pi
def is_raspberry_pi():
    try:
        with open("/proc/cpuinfo", "r") as f:
            return "Raspberry Pi" in f.read()
    except FileNotFoundError:
        return False

# Use MockFactory when testing off Pi
if not is_raspberry_pi():
    from gpiozero.pins.mock import MockFactory
    Device.pin_factory = MockFactory()
    print("[ButtonHAL] Using MockFactory (not on Raspberry Pi)")
    import keyboard  # pip install keyboard

class ButtonHAL:
    def __init__(self, bus, loop, hold_time=0.5):
        self.bus = bus
        self.loop = loop
        self.hold_time = hold_time
        self.press_times = {}

        print("[ButtonHAL] Initializing buttons...")

        # Define buttons (on real Pi these are GPIO pins)
        self.button1 = Button(17)
        self.button2 = Button(27)
        self.button3 = Button(22)
        self.button4 = Button(23)
        self.volUp   = Button(5)
        self.volDown = Button(6)
        self.mainBtn = Button(24)

        self.buttons = {
            17: self.button1,
            27: self.button2,
            22: self.button3,
            23: self.button4,
            5:  self.volUp,
            6:  self.volDown,
            24: self.mainBtn
        }

        # Attach events for real hardware
        for pin, btn in self.buttons.items():
            btn.when_pressed = lambda pin=pin: self.on_press(pin)
            btn.when_released = lambda pin=pin: self.on_release(pin)

        print("[ButtonHAL] Buttons ready:", list(self.buttons.keys()))

        # If not on Pi, also start keyboard listener
        if not is_raspberry_pi():
            threading.Thread(target=self._keyboard_loop, daemon=True).start()
            print("[ButtonHAL] Keyboard mock active (a,s,d,f,q,w,e)")

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

    # 🔹 Keyboard Simulation
    def _keyboard_loop(self):
        keymap = {
            "a": 17,  # Button1
            "s": 27,  # Button2
            "d": 22,  # Button3
            "f": 23,  # Button4
            "q": 5,   # Volume Up
            "w": 6,   # Volume Down
            "e": 24   # Main Button
        }

        while True:
            for key, pin in keymap.items():
                if keyboard.is_pressed(key):
                    if pin not in self.press_times:  # only register once
                        self.on_press(pin)
                else:
                    if pin in self.press_times:  # was pressed before, now released
                        self.on_release(pin)
                        del self.press_times[pin]
            time.sleep(0.05)  # 20Hz polling