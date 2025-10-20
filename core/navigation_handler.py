class NavigationHandler:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.bus.subscribe("button_press", self.tapFunctions)
        self.bus.subscribe("button_hold", self.holdFunctions)
        self.newMode = None
    def tapFunctions(self, data):
        if self.state.current_system_mode == "Initialization":
            return
        pin = data.get("pin")
        if pin == 17:
            self.educationMode()
        if pin == 27:
            self.AccountMode()
        if pin == 22:
            self.NetworkMode()
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

    def educationMode(self):
        self.newMode = "EducationMode"
        self.changeMode()

    def AccountMode(self):
        self.newMode = "AccountMode"
        self.changeMode()

    def NetworkMode(self):
        self.newMode = "NetworkMode"
        self.changeMode()

    def changeMode(self):
        if self.newMode != self.state.current_system_mode:
            print(f"[NavigationHandler] From [{self.state.current_system_mode}] to [{self.newMode}]")
            self.state.current_system_mode = self.newMode
