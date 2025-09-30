# core/state_machine.py
class StateMachine:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state   # shared SystemState instance
        print(f"[StateMachine] Initialized in state: {self.state.current_mode}")

        self.bus.subscribe("button_press", self.on_button_press)
        self.bus.subscribe("button_hold", self.on_button_hold)
        self.bus.subscribe("button_release", self.on_button_release)

        # Speech-driven intents
        self.bus.subscribe("request_switch_state", self.on_request_switch_state)
        self.bus.subscribe("request_volume_up", self.on_request_volume_up)
        self.bus.subscribe("request_volume_down", self.on_request_volume_down)
        self.bus.subscribe("request_education_submode", self.on_request_education_submode)

    async def on_button_press(self, data):
        pin = data.get("pin")
        print(f"[StateMachine] Button {pin} pressed, "
              f"state={self.state.current_mode}, "
              f"layer={'primary' if self.state.primary else 'secondary'}")
        if pin == 24:
            await self.bus.publish("mic_tap", {"pin": pin})
        if pin == 6:
            self.state.audioIncreaseFunction()
        
        if pin == 5:
            self.state.audioDecreaseFunction()

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
                self.state.toggle_audio_functions()
    async def on_button_hold(self, data):
        pin = data.get("pin")
        if pin == 24:
            await self.bus.publish("mic_record_start", {"pin": pin})
        if not self.state.primary:
            self.state.toggle_language()
    async def on_button_release(self, data):
        pin = data.get("pin")
        duration = data.get("duration")
        if pin == 24:
            await self.bus.publish("mic_record_stop", {"pin": pin, "duration": duration})

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

    # ===== Speech intent handlers =====
    async def on_request_switch_state(self, data):
        target = (data or {}).get("state")
        print(f"[StateMachine] Speech intent → switch to '{target}'")
        if target in {"idle", "education", "scorecheck", "wifi", "volume"}:
            await self.switch_state(target)
        else:
            print(f"[StateMachine] Unknown state '{target}' (ignored)")

    async def on_request_volume_up(self, _):
        print("[StateMachine] Speech intent → volume up")
        self.state.volumeUp()

    async def on_request_volume_down(self, _):
        print("[StateMachine] Speech intent → volume down")
        self.state.volumeDown()

    async def on_request_education_submode(self, data):
        sub = (data or {}).get("submode")
        print(f"[StateMachine] Speech intent → education submode '{sub}'")
        if self.state.current_mode != "education":
            await self.switch_state("education")
        if sub in {"learn", "quiz"}:
            old = self.state.education_submode
            if old != sub:
                # Exit current submode
                await self.bus.publish(f"exit_education_{old}_mode", {"submode": old})
                self.state.education_submode = sub
                print(f"[StateMachine] Education submode: {old} → {sub}")
                # Enter requested submode
                await self.bus.publish(f"enter_education_{sub}_mode", {"submode": sub})
        else:
            print(f"[StateMachine] Unknown education submode '{sub}' (ignored)")
