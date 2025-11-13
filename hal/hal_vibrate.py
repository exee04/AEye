from gpiozero import DigitalOutputDevice
import asyncio

class VibrateHAL:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.vibrateMotor = DigitalOutputDevice(17)
        
        self.bus.subscribe("button_release", self.onButtonPress)
    async def onButtonPress(self):
        print("Running")
        self.vibrateMotor.on()
        await asyncio.sleep(0.5)
        self.vibrateMotor.off()
