import asyncio

async def thermal_monitor(self):
    """Print CPU temperature every few seconds (Raspberry Pi only)."""
    while True:
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp_str = f.readline().strip()
            temp = float(temp_str) / 1000.0
            print(f"[ThermalMonitor] CPU Temperature: {temp:.1f} °C")
        except FileNotFoundError:
            pass
        await asyncio.sleep(3)

async def main():
    state = "[Main]"
    print(f"{state} Booting system...")
if __name__ == "__main__":
    asyncio.run(main())
