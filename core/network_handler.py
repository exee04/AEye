import asyncio
import socket
import subprocess

class NetworkHandler:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        print("[NetworkHandler] Initialized")

        # Listen for Wi-Fi connect requests
        bus.subscribe("wifi_connect", self.on_connect)
        asyncio.create_task(self._monitor_network())

    async def on_connect(self, data):
        """Attempt to connect to Wi-Fi using nmcli."""
        ssid = data.get("ssid")
        password = data.get("password")
        auth_type = data.get("type", "wpa")

        if not ssid:
            print("[NetworkHandler] ERROR: SSID is None or empty. Cannot connect.")
            return

        print(f"[NetworkHandler] Connecting to SSID={ssid}, TYPE={auth_type}")

        try:
            cmd = ["nmcli", "device", "wifi", "connect", ssid]
            if password:
                cmd += ["password", password]

            subprocess.run(cmd, check=True)

            print("[NetworkHandler] Connected successfully")
            await self.bus.publish("wifi_connected", {"ssid": ssid})

        except subprocess.CalledProcessError as e:
            print(f"[NetworkHandler] Connection failed: {e}")
            await self.bus.publish("wifi_failed", {"ssid": ssid})
    async def _monitor_network(self):
        """Periodically check connection and publish status."""
        while True:
            status = self._get_network_status()
            print(f"[NetworkHandler] Network status: {status}")
            connected = status != "Offline"
            if not connected and self.state.hasConnection:
                await self.bus.publish("network_lost", {})
            elif connected and not self.state.hasConnection:
                await self.bus.publish("network_restored", {})

            
            if status != self.state.network_status:
                print(f"[NetworkHandler] Network status changed → {status}")
                self.state.network_status = status
                await self.bus.publish("network_status", {"status": status, "connected": connected})

            await asyncio.sleep(10)

    def _get_network_status(self):
        """Determine current network state."""
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2)
        except OSError:
            return "Offline"

        # Check Wi-Fi interface
        try:
            wifi_name = subprocess.check_output("iwgetid -r", shell=True, text=True).strip()
            if wifi_name:
                return f"Wi-Fi ({wifi_name})"
        except subprocess.CalledProcessError:
            pass

        # Check Ethernet
        try:
            eth_status = subprocess.check_output("cat /sys/class/net/eth0/operstate", shell=True, text=True).strip()
            if eth_status == "up":
                return "Ethernet"
        except Exception:
            pass

        return "Online (Unknown)"

