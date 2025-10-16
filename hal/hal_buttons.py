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
        self.held_flags = {}
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
            btn.when_held = lambda pin=pin: self.on_hold(pin)

        print("[ButtonHAL] Buttons ready:", list(self.buttons.keys()))

        # If not on Pi, also start keyboard listener
        if not is_raspberry_pi():
            threading.Thread(target=self._keyboard_loop, daemon=True).start()
            print("[ButtonHAL] Keyboard mock active (a,s,d,f,q,w,e)")

    def on_hold(self, pin):
        """Triggered once when hold_time is exceeded while button is held"""
        print(f"[ButtonHAL] Button {pin} is being HELD (on_hold)")
        self.held_flags[pin] = True
        asyncio.run_coroutine_threadsafe(
            self.bus.publish("button_hold", {"pin": pin, "duration": self.hold_time}),
            self.loop
        )

    def on_press(self, pin):
        """Record timestamp when button is pressed"""
        self.press_times[pin] = time.time()
        print(f"[ButtonHAL] Button {pin} pressed at {self.press_times[pin]}")

    def on_release(self, pin):
        """Handle button release (decide if it was a tap or just release after hold)"""
        pressed_at = self.press_times.get(pin, time.time())
        duration = time.time() - pressed_at
        print(f"[ButtonHAL] Button {pin} released after {duration:.2f}s")

        # Always publish release event
        if pin == 24:
            asyncio.run_coroutine_threadsafe(
                self.bus.publish("button_release", {"pin": pin, "duration": duration}),
                self.loop
            )

        if self.held_flags.get(pin, False):
            # Was a hold → already handled in on_hold, don’t double fire
            print(f"[ButtonHAL] Button {pin} released after HOLD (no tap event)")
            self.held_flags[pin] = False
        else:
            # Was a tap
            if duration < self.hold_time:
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

        # Track which keys have already triggered "held"
        held_flags = {}

        while True:
            for key, pin in keymap.items():
                if keyboard.is_pressed(key):
                    if pin not in self.press_times:
                        # first time pressed
                        self.on_press(pin)
                        self.press_times[pin] = time.time()
                        held_flags[pin] = False
                    else:
                        # check if it's now considered a hold
                        duration = time.time() - self.press_times[pin]
                        if duration >= self.hold_time and not held_flags.get(pin, False):
                            self.on_hold(pin)
                            held_flags[pin] = True
                else:
                    if pin in self.press_times:
                        # key was released
                        self.on_release(pin)
                        del self.press_times[pin]
                        if pin in held_flags:
                            del held_flags[pin]

            time.sleep(0.05)  # 20Hz polling

