import json
from core.services.supabase_client import SupabaseService

class AccountService:
    def __init__(self, bus, state, supabase: "SupabaseService"):
        self.bus = bus
        self.state = state
        self.supabase = supabase
        self.table_name = "accounts"  # Change as needed

        print("[AccountService] Initialized")

        # Subscribe to events
        bus.subscribe("account_scan_qr", self.on_account_qr_scanned)
        bus.subscribe("account_logout", self.on_logout)

    async def on_account_qr_scanned(self, data):
        """Handle QR scan for account login."""
        qr_data = data.get("content")
        if not qr_data:
            print("[AccountService] ❌ No QR content provided.")
            await self.bus.publish("login_failed", {"error": "empty_qr"})
            return

        try:
            # Expecting something like: {"uuid": "...", "username": "..."}
            creds = json.loads(qr_data)
            uuid = creds.get("uuid")
            username = creds.get("username")
            print(f"[AccountService] Scanned QR: UUID={uuid}, USERNAME={username}")

            if not uuid or not username:
                raise ValueError("Invalid QR format")

            valid = self.supabase.check_login(self.table_name, uuid, username)

            if valid:
                print("[AccountService] ✅ Login successful")
                self.state.logged_in_user = {"uuid": uuid, "username": username}
                await self.bus.publish("login_success", {"uuid": uuid, "username": username})
            else:
                print("[AccountService] ❌ Login failed")
                await self.bus.publish("login_failed", {"uuid": uuid, "username": username})

        except Exception as e:
            print(f"[AccountService] ⚠️ Error processing QR: {e}")
            await self.bus.publish("login_failed", {"error": str(e)})

    async def on_logout(self, data=None):
        """Handle logout (clear state + notify)."""
        print("[AccountService] Logging out user")
        self.state.logged_in_user = None
        await self.bus.publish("logout_complete", {})

