import json

class AccountHandler:
    def __init__(self, bus, state):
        self.state = state
        self.bus = bus
        self.user_id = None
        self.username = None
        print("[AccountHandler] Initialized")
        self.bus.subscribe("account_connect", self.load_from_qr)
        

    def load_from_qr(self, qrdata):
        """
        Parses QR data (JSON string) and updates the state with user info.
        Expected format:
        {
            "id": "uuid-string",
            "email": "example@gmail.com",
            "username": "TonyTheTiger"
        }
        """
        try:
            data = json.loads(qrdata.get("raw"))
            self.user_id = data.get("id")
            self.username = data.get("username")

            if self.user_id and self.username:
                self.state.hasAccount = True
                print(f"[AccountHandler] Account loaded: {self.username} ({self.user_id})")
            else:
                print("[AccountHandler] Invalid QR data: missing fields")
        except json.JSONDecodeError:
            print("[AccountHandler] Failed to decode QR data")

    def clear_account(self):
        """Resets account-related info."""
        self.user_id = None
        self.username = None
        self.state.hasAccount = False
        self.state.accountInfo = None
        print("[AccountHandler] Account cleared")
