import threading
import subprocess
import asyncio

class NavigationHandler:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state

        # Local tracking for edu mode swap (Idle → Learn → Quiz)
        self.edu_modes = ["Idle", "Learn", "Quiz"]
        self.edu_index = 0  # starts at Idle

        # -------- SUBSCRIPTIONS --------
        self.bus.subscribe("button_press", self.tapFunctions)
        self.bus.subscribe("button_hold", self.holdFunctions)
        self.bus.subscribe("button_release", self.releaseFunctions)

    # ===============================================================
    #  BUTTON TAP HANDLING
    # ===============================================================
    async def tapFunctions(self, data):
        if self.state.current_system_mode == "Initialization":
            return

        pin = data.get("pin")

        # ------------------------------------------------------------------
        # MAIN BUTTON TAP (PIN 25)
        # ------------------------------------------------------------------
        if pin == 25:
            if self.state.current_system_mode == "EducationMode":
                # direct → let EducationMode handle the tap
                await self.bus.publish("education_main_tap", {"pin": 25})
            else:
                # default behaviour everywhere else
                await self.bus.publish("mic_tap", {"pin": 25})
            return

        # ------------------------------------------------------------------
        # BUTTON 27 → EDUCATION MODE CYCLE
        # ------------------------------------------------------------------
        if pin == 27:
            if self.state.current_system_mode != "EducationMode":
                # entering education mode fresh
                await self.changeMode("EducationMode")
            else:
                # cycle inside education mode
                self.cycleEducationMode()
            return

        # ------------------------------------------------------------------
        # OTHER MODE SELECT BUTTONS
        # ------------------------------------------------------------------
        if pin == 22:
            await self.changeMode("AccountMode")

        if pin == 23:
            await self.changeMode("NetworkMode")

        if pin == 24:
            self.state.current_system_mode = "Idle"

        # ------------------------------------------------------------------
        # AUDIO BUTTONS
        # ------------------------------------------------------------------
        if pin == 16:
            await self.state.AudioFunctionUp()

        if pin == 26:
            await self.state.AudioFunctionDown()

    # ===============================================================
    #  BUTTON HOLD HANDLING
    # ===============================================================
    async def holdFunctions(self, data):
        if self.state.current_system_mode == "Initialization":
            return

        pin = data.get("pin")

        # MAIN BUTTON HOLD → Start recording
        if pin == 25:
            await self.bus.publish("mic_record_start", {"pin": pin})
            return

        # These will be filled with real actions later:
        if pin == 27:
            pass  # reserved for future "discard braille paper" logic
        if pin == 22:
            pass  # reserved for "log out"
        if pin == 23:
            pass  # reserved for "disconnect wifi"
        if pin == 24:
            pass  # reserved for "shutdown"

        if pin == 16:
            await self.state.AudioFunctionToggle()

        if pin == 26:
            pass  # reserved for "swap ENG/FIL"

    # ===============================================================
    #  BUTTON RELEASE HANDLING
    # ===============================================================
    async def releaseFunctions(self, data):
        if self.state.current_system_mode == "Initialization":
            return

        pin = data.get("pin")
        duration = data.get("duration")

        if pin == 25:
            await self.bus.publish("mic_record_stop", {
                "pin": pin,
                "duration": duration
            })

    # ===============================================================
    #  EDUCATION MODE CYCLER
    # ===============================================================
    def cycleEducationMode(self):
        """Cycles Idle → Learn → Quiz → Idle ... while in EducationMode"""
        self.edu_index = (self.edu_index + 1) % len(self.edu_modes)
        new_mode = self.edu_modes[self.edu_index]
        print(f"[NavigationHandler] EducationMode switched to [{new_mode}]")

        # publish safely from sync context
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        asyncio.run_coroutine_threadsafe(
            self.bus.publish("education_mode_changed", {"mode": new_mode}),
            loop
        )

    # ===============================================================
    #  SYSTEM MODE SWITCHING
    # ===============================================================
    async def changeMode(self, newMode):
        if newMode != self.state.current_system_mode:
            print(f"[NavigationHandler] From [{self.state.current_system_mode}] to [{newMode}]")

            await self.bus.publish(f"exit_{self.state.current_system_mode}")

            self.state.current_system_mode = newMode

            # When entering EducationMode, reset EDU cycle to Idle
            if newMode == "EducationMode":
                self.edu_index = 0
                await self.bus.publish("education_mode_changed", {"mode": "Idle"})

            await self.bus.publish(f"enter_{self.state.current_system_mode}")

        else:
            print(f"[NavigationHandler] Already in {self.state.current_system_mode}")

    # ===============================================================
    #  TTS (fixed signature)
    # ===============================================================
    async def TTS(self, text):
        """Run espeak-ng in non-blocking thread from inside async code."""
        threading.Thread(
            target=lambda: subprocess.run([
                "espeak-ng",
                "-a", str(self.state.volume),
                "-s", str(self.state.voiceSpeed),
                "-p", "70",
                text
            ])
        ).start()

