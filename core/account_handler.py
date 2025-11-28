import json

class AccountHandler:
    def __init__(self, bus, state):
        self.state = state
        self.bus = bus
        self.user_id = None
        self.username = None
        print("[AccountHandler] Initialized")
        self.bus.subscribe("account_connect", self.load_from_qr)
        
    def clear_account(self):
        """Resets account-related info."""
        self.user_id = None
        self.username = None
        self.state.hasAccount = False
        self.state.accountInfo = None
        print("[AccountHandler] Account cleared")

    def load_from_qr(self, qrdata):
        try:
            data = json.loads(qrdata.get("raw"))

            self.user_id = data.get("id")
            self.username = data.get("username")

            if self.user_id and self.username:
                self.state.hasAccount = True

                # -----------------------------------------
                # STORE INTO SYSTEM STATE (NEW)
                # -----------------------------------------
                self.state.accountInfo = {
                    "id": self.user_id,
                    "username": self.username,
                    "email": data.get("email")
                }

                self.state.current_user_uuid = self.user_id
                self.state.current_username = self.username

                print(f"[AccountHandler] Account loaded:{self.username} ({self.user_id})")

            else:
                print("[AccountHandler] Invalid QR data: missing fields")

        except json.JSONDecodeError:
            print("[AccountHandler] Failed to decode QR data")

