# core/state_machine.py
class StateMachine:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state   # shared SystemState instance
        print(f"[StateMachine] Initialized in state: {self.state.current_mode}")

        self.bus.subscribe("button_press", self.on_button_press)

    async def on_button_press(self, data):
        pin = data.get("pin")
        print(f"[StateMachine] Button {pin} pressed, "
              f"state={self.state.current_mode}, "
              f"layer={'primary' if self.state.primary else 'secondary'}")
        if pin == 6:
            self.state.volumeUp()
        
        if pin == 5:
            self.state.volumeDown()

        if pin == 23:  # toggle primary/secondary
            self.state.toggle_layer()
            if self.state.current_mode != "idle":
                await self.switch_state("idle")

            if self.state.education_submode != "idle":
                print(f"[StateMachine] Resetting education submode → idle")
                self.state.education_submode = "idle"

        elif self.state.primary:
            if pin == 17:
                await self.switch_state("education")
            elif pin == 27:
                await self.switch_state("scorecheck")
            elif pin == 22 and self.state.current_mode == "education":
                await self.cycle_education_submode()

        else:  # secondary layer
            if pin == 17:
                await self.switch_state("wifi")
            elif pin == 27:
                await self.switch_state("volume")

    async def switch_state(self, new_state):
        """Switch top-level states (education, scorecheck, wifi, volume)"""
        if self.state.current_mode != new_state:
            # exit old state
            await self.bus.publish(f"exit_{self.state.current_mode}_mode",
                                   {"state": self.state.current_mode})

            print(f"[StateMachine] Switching {self.state.current_mode} → {new_state}")
            self.state.switch_mode(new_state)

            # enter new state
            await self.bus.publish(f"enter_{new_state}_mode", {"state": new_state})

    async def cycle_education_submode(self):
        """Cycle through Idle → Learn → Quiz sub-modes"""
        old = self.state.education_submode
        self.state.cycle_education_submode()

        # exit current submode
        await self.bus.publish(f"exit_education_{old}_mode", {"submode": old})
        # enter new submode
        await self.bus.publish(f"enter_education_{self.state.education_submode}_mode",
                               {"submode": self.state.education_submode})
