#!/bin/bash
# Quick Start Script for Linux/Mac - Arduino Temperature Integration
# Run this to start the dashboard with Arduino temperature sensor

echo "============================================================"
echo "Tilapiers Dashboard - Arduino Temperature Integration"
echo "============================================================"
echo ""

# Check if pyserial is installed
python3 -c "import serial" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[!] Installing required Python package: pyserial"
    pip3 install pyserial
    echo ""
fi

# Set your Arduino port here
# Linux: Usually /dev/ttyUSB0 or /dev/ttyACM0
# Mac: Usually /dev/cu.usbserial-* or /dev/cu.usbmodem*
ARDUINO_PORT="/dev/ttyUSB0"

echo "[*] Arduino Port: $ARDUINO_PORT"
echo "[*] Change the ARDUINO_PORT variable in this file if needed"
echo ""

# Check if port exists
if [ ! -e "$ARDUINO_PORT" ]; then
    echo "[!] Warning: Port $ARDUINO_PORT not found"
    echo "[*] Available ports:"
    ls /dev/tty{USB,ACM}* 2>/dev/null || echo "    No USB serial ports found"
    echo ""
fi

# Check permissions (Linux only)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if [ ! -w "$ARDUINO_PORT" ]; then
        echo "[!] Permission denied for $ARDUINO_PORT"
        echo "[*] Run: sudo chmod 666 $ARDUINO_PORT"
        echo "[*] Or add user to dialout group: sudo usermod -a -G dialout $USER"
        echo ""
    fi
fi

echo "[*] Starting dashboard..."
cd Aqua_Scan/tilapiers

# Edit start_with_arduino.py to set the port
sed -i "s/ARDUINO_PORT = .*/ARDUINO_PORT = '$ARDUINO_PORT'/" start_with_arduino.py 2>/dev/null

python3 start_with_arduino.py
