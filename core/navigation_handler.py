import os
import threading

class NavigationHandler:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.bus.subscribe("button_press", self.tapFunctions)
        self.bus.subscribe("button_hold", self.holdFunctions)
        self.bus.subscribe("button_release", self.releaseFunctions)

    async def tapFunctions(self, data):
        if self.state.current_system_mode == "Initialization":
            return
        pin = data.get("pin")
        if pin == 25:
            await self.bus.publish("mic_tap", {"pin": pin})
        if pin == 27:
            await self.changeMode("EducationMode")
        if pin == 22:
            await self.changeMode("AccountMode")
        if pin == 23:
            await self.changeMode("NetworkMode")
        if pin == 24:
            self.state.current_system_mode = "Idle"

    async def holdFunctions(self, data):
        if self.state.current_system_mode == "Initialization":
            return
        pin = data.get("pin")
        print(pin)
        if pin == 25:
            print("wa")
            await self.bus.publish("mic_record_start", {"pin": pin})
        if pin == 27:
            print("Discard Current Braille Paper")
        if pin == 22:
            print("Log out account")
        if pin == 23:
            print("Disconnect current wifi")
        if pin == 24:
            print("Shutdown")
        if pin == 6:
            print("Swap between volume and voice speed")
        if pin == 5:
            print("Swap between english and filipino")

    async def releaseFunctions(self, data):
        if self.state.current_system_mode == "Initialization":
            return
        pin = data.get("pin")
        duration = data.get("duration")
        if pin == 25:
            await self.bus.publish("mic_record_stop", {"pin": pin, "duration": duration})

    async def changeMode(self, newMode):
        if newMode != self.state.current_system_mode:
            print(f"[NavigationHandler] From [{self.state.current_system_mode}] to [{newMode}]")
            await self.bus.publish(f"exit_{self.state.current_system_mode}")
            self.state.current_system_mode = newMode
            await self.bus.publish(f"enter_{self.state.current_system_mode}")
        else:
            print(f"[NavigationHandler] Already in {self.state.current_system_mode}")

    def TTS(text, self):
        threading.Thread(target=lambda: subprocess.run([
            'espeak-ng',
            "-a", str(self.state.volume),
            "-s", str(self.state.voiceSpeed),
            "-p", "70",
            text
        ])).start()
