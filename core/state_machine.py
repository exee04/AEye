# core/state_machine.py

class StateMachine:
    def __init__(self, bus):
        self.bus = bus
        self.current_state = "idle"
        self.primary = True
        self.education_submode = "idle"  # start at idle
        print(f"[StateMachine] Initialized in state: {self.current_state}")

        self.bus.subscribe("button_press", self.on_button_press)

    async def on_button_press(self, data):
        pin = data.get("pin")
        print(f"[StateMachine] Button {pin} pressed, state={self.current_state}, layer={'primary' if self.primary else 'secondary'}")

        if pin == 23:  # toggle primary/secondary
            self.primary = not self.primary
            print(f"[StateMachine] Layer switched → {'primary' if self.primary else 'secondary'}")

        elif self.primary:
            if pin == 17:
                await self.switch_state("education")
            elif pin == 27:
                await self.switch_state("scorecheck")
            elif pin == 22 and self.current_state == "education":
                await self.cycle_education_submode()

        else:  # secondary layer
            if pin == 17:
                await self.switch_state("wifi")
            elif pin == 27:
                await self.switch_state("volume")

    async def switch_state(self, new_state):
        """Switch top-level states (education, scorecheck, wifi, volume)"""
        if self.current_state != new_state:
            # exit old state
            await self.bus.publish(f"exit_{self.current_state}_mode", {"state": self.current_state})

            print(f"[StateMachine] Switching {self.current_state} → {new_state}")
            self.current_state = new_state

            # enter new state
            await self.bus.publish(f"enter_{new_state}_mode", {"state": new_state})

    async def cycle_education_submode(self):
        """Cycle through Idle → Learn → Quiz sub-modes"""
        sequence = ["idle", "learn", "quiz"]
        idx = sequence.index(self.education_submode)
        next_idx = (idx + 1) % len(sequence)
        next_mode = sequence[next_idx]

        # exit current submode
        await self.bus.publish(f"exit_education_{self.education_submode}_mode", {"submode": self.education_submode})
        print(f"[StateMachine] Exiting sub-mode: {self.education_submode}")

        # enter next submode
        self.education_submode = next_mode
        print(f"[StateMachine] Entering sub-mode: {self.education_submode}")
        await self.bus.publish(f"enter_education_{next_mode}_mode", {"submode": next_mode})
