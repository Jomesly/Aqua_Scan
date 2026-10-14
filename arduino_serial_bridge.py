"""
Arduino Serial Bridge for Tilapiers
Reads temperature data from Arduino DS18B20 sensor via serial port
and makes it available to the FastAPI backend
"""

import serial
import json
import time
import threading
from datetime import datetime
from typing import Optional, Dict
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ArduinoTemperatureBridge:
    """Bridge between Arduino temperature sensor and the dashboard backend"""

    def __init__(self, port: str = 'COM3', baudrate: int = 115200):
        """
        Initialize the Arduino serial bridge

        Args:
            port: Serial port (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux)
            baudrate: Serial communication speed (must match Arduino)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self.latest_data: Dict = {
            'status': 'disconnected',
            'temperature_c': None,
            'temperature_f': None,
            'last_update': None,
            'error': 'Not connected'
        }
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def connect(self) -> bool:
        """Connect to the Arduino serial port"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1
            )
            time.sleep(2)  # Wait for Arduino to reset after connection
            logger.info(f"Connected to Arduino on {self.port}")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to Arduino: {e}")
            self.latest_data['error'] = str(e)
            return False

    def disconnect(self):
        """Disconnect from the Arduino"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("Disconnected from Arduino")

    def _read_loop(self):
        """Background thread that continuously reads from Arduino"""
        logger.info("Starting Arduino read loop")

        while self.running:
            try:
                if not self.serial_conn or not self.serial_conn.is_open:
                    logger.warning("Serial connection lost, attempting reconnect...")
                    if not self.connect():
                        time.sleep(5)
                        continue

                # Read line from serial
                if self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode('utf-8').strip()

                    if line:
                        try:
                            # Parse JSON data from Arduino
                            data = json.loads(line)

                            if data.get('status') == 'ok':
                                self.latest_data = {
                                    'status': 'connected',
                                    'temperature_c': data.get('temperature_c'),
                                    'temperature_f': data.get('temperature_f'),
                                    'last_update': datetime.now().isoformat(),
                                    'source': data.get('source', 'arduino'),
                                    'error': None
                                }
                                logger.debug(f"Temperature update: {self.latest_data['temperature_c']}°C")
                            else:
                                # Error from Arduino
                                self.latest_data['status'] = 'error'
                                self.latest_data['error'] = data.get('message', 'Unknown error')
                                logger.warning(f"Arduino error: {self.latest_data['error']}")

                        except json.JSONDecodeError as e:
                            logger.warning(f"Invalid JSON from Arduino: {line} - {e}")

            except Exception as e:
                logger.error(f"Error in read loop: {e}")
                self.latest_data['status'] = 'error'
                self.latest_data['error'] = str(e)
                time.sleep(1)

            time.sleep(0.1)  # Small delay to prevent CPU spinning

        logger.info("Arduino read loop stopped")

    def start(self):
        """Start the background reading thread"""
        if self.running:
            logger.warning("Bridge already running")
            return

        if not self.connect():
            logger.error("Failed to start bridge: could not connect to Arduino")
            return

        self.running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
        logger.info("Arduino bridge started")

    def stop(self):
        """Stop the background reading thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.disconnect()
        logger.info("Arduino bridge stopped")

    def get_temperature(self) -> Dict:
        """Get the latest temperature reading"""
        return self.latest_data.copy()


# Global instance
_bridge: Optional[ArduinoTemperatureBridge] = None


def get_bridge() -> ArduinoTemperatureBridge:
    """Get or create the global Arduino bridge instance"""
    global _bridge
    if _bridge is None:
        _bridge = ArduinoTemperatureBridge()
    return _bridge


def start_bridge(port: str = 'COM3', baudrate: int = 115200):
    """Start the Arduino temperature bridge"""
    bridge = get_bridge()
    bridge.port = port
    bridge.baudrate = baudrate
    bridge.start()
    return bridge


def stop_bridge():
    """Stop the Arduino temperature bridge"""
    if _bridge:
        _bridge.stop()


if __name__ == '__main__':
    # Test the bridge standalone
    import sys

    port = sys.argv[1] if len(sys.argv) > 1 else 'COM3'

    print(f"Starting Arduino Temperature Bridge on {port}")
    print("Press Ctrl+C to stop\n")

    bridge = ArduinoTemperatureBridge(port=port)
    bridge.start()

    try:
        while True:
            data = bridge.get_temperature()
            print(f"\rTemp: {data.get('temperature_c')}°C | "
                  f"Status: {data.get('status')} | "
                  f"Last: {data.get('last_update', 'Never')}", end='')
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping bridge...")
        bridge.stop()
        print("Bridge stopped")
