class NavigationHandler:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.bus.subscribe("button_press", self.tapNavigation)
        self.newMode = None
    def tapNavigation(self, data):
        if self.state.current_system_mode == "Initialization":
            return
        pin = data.get("pin")
        if pin == 17:
            self.state.current_system_mode = "Educ"
            print(self.state.current_system_mode)
            self.educationMode()
        if pin == 27:
            self.scoreCheckMode()
        if pin == 22:
            self.networkMode()
        if pin == 23:
            self.state.current_system_mode = "Idle"

    def educationMode(self):
        self.newMode = "EducationMode"
        self.changeMode()

    def scoreCheckMode():
        return

    def networkMode():
        return

    async def changeMode(self):
        if self.current_system_modenewMode != self.state.current_system_mode:
            self.current_system_mode = self.newMode
            print(f"[NavigationHandler] From [{self.state.current_system_mode}] to [{self.newMode}]")
