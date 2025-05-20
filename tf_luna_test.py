import serial
import time
import struct
import logging
import subprocess
from gpiozero import DigitalOutputDevice, DigitalInputDevice

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TFLuna:
    def __init__(self, port='/dev/serial0', baudrate=115200):
        """
        Initialize TF-Luna LiDAR sensor
        :param port: Serial port (default: '/dev/serial0' for Raspberry Pi GPIO)
        :param baudrate: Baud rate (default: 115200)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.frame_header = 0x5A
        self.frame_length = 9
        
        # Configure GPIO pins using gpiozero
        self.txd = DigitalOutputDevice(14)  # GPIO 14 for TXD
        self.rxd = DigitalInputDevice(15)   # GPIO 15 for RXD

    def check_uart_availability(self):
        """Check if UART is available and not being used by agetty"""
        try:
            result = subprocess.run(['lsof', '/dev/ttyAMA0'], capture_output=True, text=True)
            if 'agetty' in result.stdout:
                logger.warning("UART is being used by agetty. Please disable it by running:")
                logger.warning("sudo systemctl disable serial-getty@ttyAMA0.service")
                logger.warning("sudo systemctl stop serial-getty@ttyAMA0.service")
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking UART availability: {e}")
            return False

    def connect(self):
        """Connect to the TF-Luna sensor"""
        try:
            # Check UART availability
            if not self.check_uart_availability():
                return False

            # Enable serial port on Raspberry Pi
            config_path = '/boot/firmware/config.txt'  # Updated path for newer Raspberry Pi OS
            with open(config_path, 'r') as f:
                config = f.read()
            
            if 'enable_uart=1' not in config:
                logger.warning(f"UART not enabled in {config_path}. Please enable it by adding 'enable_uart=1'")
                logger.warning("After enabling UART, you'll need to reboot the Raspberry Pi")
                return False
            
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            logger.info(f"Connected to TF-Luna on {self.port}")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to TF-Luna: {e}")
            return False

    def disconnect(self):
        """Disconnect from the TF-Luna sensor"""
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("Disconnected from TF-Luna")
        # Clean up GPIO
        self.txd.close()
        self.rxd.close()

    def read_data(self):
        """
        Read a single frame of data from the TF-Luna
        :return: Dictionary containing distance, signal strength, and temperature
        """
        if not self.serial or not self.serial.is_open:
            logger.error("Serial port not open")
            return None

        try:
            # Read until we find the frame header
            while True:
                if self.serial.in_waiting >= self.frame_length:
                    header = self.serial.read()
                    if header[0] == self.frame_header:
                        break
                    self.serial.read(self.serial.in_waiting)

            # Read the rest of the frame
            frame = self.serial.read(self.frame_length - 1)
            
            # Parse the data
            distance = struct.unpack('<H', frame[0:2])[0]  # Distance in cm
            signal_strength = struct.unpack('<H', frame[2:4])[0]  # Signal strength
            temperature = struct.unpack('<H', frame[4:6])[0] / 8.0  # Temperature in °C

            return {
                'distance': distance,
                'signal_strength': signal_strength,
                'temperature': temperature
            }

        except serial.SerialException as e:
            logger.error(f"Error reading from TF-Luna: {e}")
            return None

def main():
    # Create TF-Luna instance
    tf_luna = TFLuna()
    
    # Connect to the sensor
    if not tf_luna.connect():
        return

    try:
        print("Reading TF-Luna data. Press Ctrl+C to stop.")
        print("Make sure the TF-Luna is connected to:")
        print("  - GPIO 14 (TXD) -> TF-Luna RX")
        print("  - GPIO 15 (RXD) -> TF-Luna TX")
        print("  - GND -> TF-Luna GND")
        print("  - 5V -> TF-Luna VCC")
        print("-" * 50)
        
        while True:
            data = tf_luna.read_data()
            if data:
                print(f"Distance: {data['distance']} cm")
                print(f"Signal Strength: {data['signal_strength']}")
                print(f"Temperature: {data['temperature']:.1f}°C")
                print("-" * 30)
            time.sleep(0.1)  # Small delay to prevent overwhelming the serial port

    except KeyboardInterrupt:
        print("\nStopping TF-Luna test")
    finally:
        tf_luna.disconnect()

if __name__ == "__main__":
    main() 