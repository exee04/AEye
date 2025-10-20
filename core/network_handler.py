import subprocess
import asyncio
import socket


class NetworkHandler:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        print("[NetworkHandler] Initialized")
        # Subscribe to wifi connect/disconnect requests
        bus.subscribe("wifi_connect", self.on_connect)
        asyncio.create_task(self._monitor_network())

    async def on_connect(self, data):
        ssid = data.get("ssid")
        password = data.get("password")
        auth_type = data.get("type", "wpa")

        print(f"[NetworkHandler] Connecting to SSID={ssid}, TYPE={auth_type}")

        try:
            cmd = ["nmcli", "device", "wifi", "connect", ssid]
            if password:
                cmd += ["password", password]

            subprocess.run(cmd, check=True)
            print("[WifiService] Connected successfully")
            await self.bus.publish("wifi_connected", {"ssid": ssid})

        except subprocess.CalledProcessError as e:
            print(f"[WifiService] Connection failed: {e}")
            await self.bus.publish("wifi_failed", {"ssid": ssid, "error": str(e)})

    async def _monitor_network(self):
        while True:
            status = self._get_network_status()
            if status != self.state.network_status:
                print(f"[NetworkService] Network status changed → {status}")
                self.state.network_status = status
                await self.bus.publish("network_status", {"status": status})
            await asyncio.sleep(10)  # check every 10 seconds

    def _get_network_status(self):
        """Check if online, and whether via Ethernet or Wi-Fi"""
        try:
            # Quick check if internet is reachable
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            self.state.hasConnection = True
        except OSError:
            return "Offline"

        # Check interface
        try:
            result = subprocess.check_output(
                "iwgetid -r", shell=True, text=True
            ).strip()
            if result:
                return f"Wi-Fi ({result})"
        except subprocess.CalledProcessError:
            pass

        # Check Ethernet
        try:
            eth_status = subprocess.check_output(
                "cat /sys/class/net/eth0/operstate", shell=True, text=True
            ).strip()
            if eth_status == "up":
                return "Ethernet"
        except Exception:
            pass
        return "Online (Unknown)"
