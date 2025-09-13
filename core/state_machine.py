# core/state_machine.py

class StateMachine:
    def __init__(self, bus):
        self.bus = bus
        self.layer = "primary"
        self.current_state = "idle"
        self.sub_state = None  # for education sub-modes
        print(f"[StateMachine] Initialized in state: {self.current_state}")

        # Subscribe to button press events
        self.bus.subscribe("button_press", self.on_button_press)

    async def on_button_press(self, data):
        pin = data["pin"]
        print(f"[StateMachine] Button {pin} pressed in state {self.current_state} ({self.layer} layer)")

        # 🔹 Layer toggle
        if pin == 23:
            self.layer = "secondary" if self.layer == "primary" else "primary"
            print(f"[StateMachine] Layer switched → {self.layer}")
            return

        # 🔹 Primary layer
        if self.layer == "primary":
            if pin == 17:  # Education Mode
                await self.switch_state("education")
            elif pin == 27:  # Score Check Mode
                await self.switch_state("scorecheck")
            elif pin == 22:  # Contextual function button
                if self.current_state == "education":
                    await self.cycle_education_mode()
                elif self.current_state == "scorecheck":
                    await self.bus.publish("scorecheck_extra_action", {"pin": 22})

        # 🔹 Secondary layer
        else:
            if pin == 17:  # Education still available
                await self.switch_state("education")
            elif pin == 27:  # Wi-Fi Mode
                await self.switch_state("wifi")
            elif pin == 22:  # Volume Mode
                await self.switch_state("volume")

    async def cycle_education_mode(self):
        """Cycle between idle, learn, quiz inside Education"""
        modes = ["idle", "learn", "quiz"]
        if self.sub_state is None:
            self.sub_state = "idle"
        else:
            idx = (modes.index(self.sub_state) + 1) % len(modes)
            self.sub_state = modes[idx]

        print(f"[StateMachine] Education sub-mode → {self.sub_state}")
        await self.bus.publish(f"enter_education_{self.sub_state}_mode", {"state": self.sub_state})

    async def switch_state(self, new_state):
        if self.current_state == new_state:
            print(f"[StateMachine] Already in {new_state}, ignoring")
            return

        # Exit old state
        if self.current_state != "idle":
            await self.bus.publish(f"exit_{self.current_state}_mode", {"state": self.current_state})

        print(f"[StateMachine] Switching {self.layer} → {new_state}")
        self.current_state = new_state
        self.sub_state = None  # reset when leaving education
        await self.bus.publish(f"enter_{new_state}_mode", {"state": new_state})
