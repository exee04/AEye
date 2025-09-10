# core/state_machine.py

class StateMachine:
    def __init__(self, bus):
        self.bus = bus
        self.current_state = "idle"
        self.primary = True
        print(f"[StateMachine] Initialized in state: {self.current_state}")

        # Subscribe to button press events
        self.bus.subscribe("button_press", self.on_button_press)

    async def on_button_press(self, data):
        """Handle button press and decide what to do"""
        pin = data.get("pin")
        print(f"[StateMachine] Button pressed on pin {pin} while in state {self.current_state}")

        if pin == 23:
            self.primary = not self.primary
        if pin == 17:
            await self.switch_state("learn") if self.primary else self.switch_state("battery")
        elif pin == 27:
            await self.switch_state("quiz")
        elif pin == 23:
            await self.switch_state("primary")

    async def switch_state(self, new_state):
        """Switch modes and notify subscribers"""
        print(f"[StateMachine] Switching from {self.current_state} → {new_state}")
        self.current_state = new_state

        # Publish an event for other modules (modes) to listen to
        await self.bus.publish(f"enter_{new_state}_mode", {"state": new_state})

   
        
