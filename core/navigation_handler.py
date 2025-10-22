class NavigationHandler:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.bus.subscribe("button_press", self.tapFunctions)
        self.bus.subscribe("button_hold", self.holdFunctions)

    async def tapFunctions(self, data):
        if self.state.current_system_mode == "Initialization":
            return
        pin = data.get("pin")
        if pin == 17:
            await self.changeMode("EducationMode")
        if pin == 27:
            await self.changeMode("AccountMode")
        if pin == 22:
            await self.changeMode("NetworkMode")
        if pin == 23:
            self.state.current_system_mode = "Idle"

    def holdFunctions(self, data):
        if self.state.current_system_mode == "Initialization":
            return
        pin = data.get("pin")
        if pin == 17:
            print("Discard Current Braille Paper")
        if pin == 27:
            print("Log out account")
        if pin == 22:
            print("Disconnect current wifi")
        if pin == 23:
            print("Shutdown")
        if pin == 6:
            print("Swap between volume and voice speed")
        if pin == 5:
            print("Swap between english and filipino")

    async def changeMode(self, newMode):
        if newMode != self.state.current_system_mode:
            print(f"[NavigationHandler] From [{self.state.current_system_mode}] to [{newMode}]")
            await self.bus.publish(f"exit_{self.state.current_system_mode}")
            self.state.current_system_mode = newMode
            await self.bus.publish(f"enter_{self.state.current_system_mode}")
        else:
            print(f"[NavigationHandler] Already in {self.state.current_system_mode}")
