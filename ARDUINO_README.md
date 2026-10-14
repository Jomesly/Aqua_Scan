# Arduino Temperature Sensor Integration for Tilapiers Dashboard

This integration connects your Arduino DS18B20 temperature sensor to the Tilapiers intelligent feeding system dashboard, providing real-time water temperature monitoring.

## 🔧 Hardware Requirements

- Arduino board (Uno, Nano, ESP32, etc.)
- DS18B20 waterproof temperature sensor
- 4.7kΩ resistor (pull-up for DS18B20)
- 16x2 I2C LCD display (optional, for local display)
- USB cable
- Breadboard and jumper wires

## 📐 Wiring Diagram

```
DS18B20 Temperature Sensor:
  - VCC (Red)    → Arduino 5V
  - GND (Black)  → Arduino GND
  - DATA (Yellow)→ Arduino GPIO 4
  - 4.7kΩ resistor between VCC and DATA

I2C LCD (optional):
  - VCC → Arduino 5V
  - GND → Arduino GND
  - SDA → Arduino A4 (or SDA pin)
  - SCL → Arduino A5 (or SCL pin)
```

## 📦 Installation

### 1. Arduino Setup

1. **Install Arduino IDE** (if not already installed): https://www.arduino.cc/en/software

2. **Install Required Arduino Libraries:**
   - Open Arduino IDE
   - Go to `Sketch` → `Include Library` → `Manage Libraries`
   - Search and install:
     - `OneWire` by Paul Stoffregen
     - `DallasTemperature` by Miles Burton
     - `LiquidCrystal I2C` by Frank de Brabander
     - `ArduinoJson` by Benoit Blanchon

3. **Upload the Code:**
   - Open `arduino_temp_sensor.ino`
   - Connect your Arduino via USB
   - Select your board: `Tools` → `Board`
   - Select your port: `Tools` → `Port` (e.g., COM3)
   - Click Upload button (→)

4. **Find Your COM Port:**
   - **Windows**: Device Manager → Ports (COM & LPT) → Note the COM# (e.g., COM3)
   - **Linux**: Run `ls /dev/ttyUSB*` or `ls /dev/ttyACM*`
   - **Mac**: Run `ls /dev/cu.*`

### 2. Python Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r arduino_requirements.txt
   ```
   Or manually:
   ```bash
   pip install pyserial
   ```

2. **Test the Serial Bridge:**
   ```bash
   # Windows
   python arduino_serial_bridge.py COM3

   # Linux/Mac
   python arduino_serial_bridge.py /dev/ttyUSB0
   ```
   
   You should see temperature readings updating every 2 seconds.

### 3. Start the Dashboard with Arduino

**Option A: Using the startup script (Recommended)**

Edit `Aqua_Scan/tilapiers/start_with_arduino.py`:
```python
ARDUINO_PORT = 'COM3'  # Change to your actual port
```

Then run:
```bash
cd Aqua_Scan/tilapiers
python start_with_arduino.py
```

**Option B: Manual integration**

Edit `Aqua_Scan/tilapiers/live_dashboard.py` and add at the bottom (before `if __name__ == "__main__"`):

```python
from arduino_integration import initialize_arduino

# Initialize Arduino on startup
initialize_arduino(port='COM3', baudrate=115200)  # Change COM3 to your port
```

Then start normally:
```bash
cd Aqua_Scan/tilapiers
python live_dashboard.py
```

## 🚀 Usage

1. **Start the System:**
   - Ensure Arduino is plugged in and powered on
   - Run the startup script or dashboard
   - Open your browser to http://127.0.0.1:8000

2. **Verify Connection:**
   - Check the Environmental Parameters section
   - Temperature should update every 2 seconds
   - No "Simulated" badge should appear if Arduino is connected
   - LCD on Arduino should display temperature in °C and °F

3. **Monitor Temperature:**
   - Dashboard shows real-time temperature from Arduino
   - System checks temperature against safe range (25-31°C)
   - Feeding is withheld if temperature is outside safe range
   - SMS alerts sent if unsafe conditions detected

## 📊 How It Works

```
Arduino DS18B20 Sensor
       ↓
Serial Port (115200 baud)
       ↓
arduino_serial_bridge.py (Background thread)
       ↓
arduino_integration.py
       ↓
telemetry.py (sensor_worker)
       ↓
Dashboard API (/api/environment)
       ↓
React Dashboard UI
```

**Data Flow:**
1. Arduino reads DS18B20 every 2 seconds
2. Sends JSON: `{"status":"ok","temperature_c":27.5,"temperature_f":81.5}`
3. Python bridge reads serial port in background thread
4. Temperature integrated into telemetry system
5. Dashboard displays real temperature
6. Feeding decisions use real temperature data

**Fallback Behavior:**
- If Arduino disconnects: System falls back to simulated temperature
- If DS18B20 sensor fails: Arduino sends error status
- System continues operating safely with simulation

## 🐛 Troubleshooting

### Arduino Not Detected

**Problem:** `Could not connect to Arduino`

**Solutions:**
1. Check USB cable is connected and Arduino powered on
2. Verify correct COM port in Device Manager (Windows) or `ls /dev/tty*` (Linux)
3. Close Arduino IDE Serial Monitor if open
4. Try unplugging and replugging Arduino
5. Check serial port permissions (Linux): `sudo chmod 666 /dev/ttyUSB0`

### Sensor Error on LCD

**Problem:** LCD shows "Temp: Sensor Error"

**Solutions:**
1. Check DS18B20 wiring (especially DATA pin to GPIO 4)
2. Verify 4.7kΩ pull-up resistor between DATA and VCC
3. Test sensor with simple Arduino sketch
4. Try different DS18B20 sensor (may be faulty)
5. Check sensor is waterproof version for aquarium use

### Temperature Shows as Simulated

**Problem:** Dashboard shows temperature with "Simulated" badge

**Solutions:**
1. Check Arduino initialization succeeded in console logs
2. Verify `pyserial` is installed: `pip install pyserial`
3. Check COM port is correct
4. Restart the dashboard application
5. Test serial bridge standalone: `python arduino_serial_bridge.py COM3`

### JSON Decode Errors

**Problem:** Console shows "Invalid JSON from Arduino"

**Solutions:**
1. Verify ArduinoJson library is installed
2. Check serial baudrate matches (115200 in both Arduino and Python)
3. Ensure no other program is reading the serial port
4. Re-upload Arduino sketch

### Permission Denied (Linux)

**Problem:** `Permission denied: '/dev/ttyUSB0'`

**Solutions:**
1. Add user to dialout group: `sudo usermod -a -G dialout $USER`
2. Log out and log back in
3. Or temporarily: `sudo chmod 666 /dev/ttyUSB0`

## 📝 Configuration

### Change Serial Port

Edit in your startup code:
```python
ARDUINO_PORT = 'COM5'  # Windows
ARDUINO_PORT = '/dev/ttyUSB0'  # Linux
ARDUINO_PORT = '/dev/cu.usbserial-14430'  # Mac
```

### Change Update Interval

Edit `arduino_temp_sensor.ino`:
```cpp
const unsigned long serialInterval = 2000; // milliseconds (2 seconds)
```

### Change Temperature Precision

Edit `arduino_temp_sensor.ino`:
```cpp
lcd.print(tempC, 2); // Change 1 to 2 for 2 decimal places
```

## 🧪 Testing

### Test Arduino Standalone
```bash
python arduino_serial_bridge.py COM3
```
Expected output:
```
Temp: 27.5°C | Status: connected | Last: 2026-10-12T06:15:23
```

### Test via Python
```python
from arduino_integration import initialize_arduino, get_arduino_temperature

# Initialize
initialize_arduino(port='COM3')

# Get reading
data = get_arduino_temperature()
print(f"Temperature: {data['temperature_c']}°C")
print(f"Status: {data['status']}")
```

### Verify Dashboard Integration
```bash
# Start dashboard
python start_with_arduino.py

# In another terminal, test API
curl http://127.0.0.1:8000/api/environment
```

Should return JSON with temperature from Arduino (no "simulated": true if connected).

## 📋 Files Created

- `arduino_temp_sensor.ino` - Arduino firmware with DS18B20 sensor
- `arduino_serial_bridge.py` - Serial communication handler
- `arduino_integration.py` - Integration layer for telemetry
- `start_with_arduino.py` - Startup script with Arduino initialization
- `arduino_requirements.txt` - Python dependencies
- `ARDUINO_SETUP_GUIDE.txt` - Detailed setup instructions
- `ARDUINO_README.md` - This file

## 🎯 Features

✅ Real-time temperature monitoring from DS18B20  
✅ Automatic fallback to simulation if Arduino disconnects  
✅ JSON-based serial communication  
✅ Background thread for non-blocking operation  
✅ LCD display for local monitoring  
✅ Integration with feeding safety gates  
✅ Error handling and recovery  
✅ Cross-platform support (Windows, Linux, Mac)  

## 🔒 Safety Notes

- DS18B20 sensor is waterproof and safe for aquarium use
- Temperature readings are used for feeding safety decisions
- System withholds feeding if temperature is outside safe range (25-31°C)
- Always verify sensor readings are accurate before relying on automated feeding
- Regularly calibrate and test sensor accuracy
- Have backup monitoring in place for critical aquaculture applications

## 📚 Additional Resources

- [DS18B20 Datasheet](https://datasheets.maximintegrated.com/en/ds/DS18B20.pdf)
- [Arduino OneWire Library](https://www.pjrc.com/teensy/td_libs_OneWire.html)
- [DallasTemperature Library](https://github.com/milesburton/Arduino-Temperature-Control-Library)
- [Tilapiers Project Documentation](./README.md)

## 🆘 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Test components individually (Arduino → Serial Bridge → Integration)
3. Check console logs for error messages
4. Verify hardware connections
5. Test with a simple DS18B20 Arduino sketch first

## 📄 License

This integration is part of the Tilapiers project. See main project license.
