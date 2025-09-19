import subprocess
import asyncio

class WifiService:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        print("[WifiService] Initialized")
        # Subscribe to wifi connect/disconnect requests
        bus.subscribe("wifi_connect", self.on_connect)
        bus.subscribe("wifi_disconnect", self.on_disconnect)
        bus.subscribe("wifi_status", self.on_status)

    async def on_connect(self, data):
        ssid = data.get("ssid")
        password = data.get("password")
        auth_type = data.get("type", "wpa")

        print(f"[WifiService] Connecting to SSID={ssid}, TYPE={auth_type}")

        try:
            # Example with nmcli (Linux Network Manager)
            cmd = ["nmcli", "device", "wifi", "connect", ssid]
            if password:
                cmd += ["password", password]

            subprocess.run(cmd, check=True)
            print("[WifiService] Connected successfully")
            await self.bus.publish("wifi_connected", {"ssid": ssid})

        except subprocess.CalledProcessError as e:
            print(f"[WifiService] Connection failed: {e}")
            await self.bus.publish("wifi_failed", {"ssid": ssid, "error": str(e)})

    async def on_disconnect(self, data=None):
        print("[WifiService] Disconnecting Wi-Fi")
        try:
            subprocess.run(["nmcli", "device", "disconnect", "wlan0"], check=True)
            await self.bus.publish("wifi_disconnected", {})
        except subprocess.CalledProcessError as e:
            print(f"[WifiService] Disconnect failed: {e}")

    async def on_status(self, data=None):
        """Check current connection status"""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                capture_output=True, text=True, check=True
            )
            active_lines = [
                line for line in result.stdout.splitlines()
                if line.startswith("yes:")
            ]
            if active_lines:
                ssid = active_lines[0].split(":")[1]
                await self.bus.publish("wifi_status_result", {"connected": True, "ssid": ssid})
            else:
                await self.bus.publish("wifi_status_result", {"connected": False})
        except Exception as e:
            await self.bus.publish("wifi_status_result", {"connected": False, "error": str(e)})