"""
Arduino Connection Diagnostic Tool
Run this to verify Arduino is sending data correctly
"""

import sys
import time

def test_arduino_connection(port='COM3'):
    """Test Arduino connection and display readings"""

    print("\n" + "="*70)
    print("ARDUINO CONNECTION DIAGNOSTIC")
    print("="*70)
    print(f"\nTesting connection on port: {port}")
    print("Press Ctrl+C to stop\n")

    # Test 1: Serial Bridge
    print("[1/3] Testing serial bridge...")
    try:
        from arduino_serial_bridge import ArduinoTemperatureBridge

        bridge = ArduinoTemperatureBridge(port=port, baudrate=115200)
        bridge.start()

        time.sleep(3)  # Wait for connection

        data = bridge.get_temperature()
        if data.get('status') == 'connected':
            print(f"  ✓ Serial bridge connected")
            print(f"  ✓ Temperature: {data.get('temperature_c')}°C")
            print(f"  ✓ Last update: {data.get('last_update')}")
        else:
            print(f"  ✗ Serial bridge status: {data.get('status')}")
            print(f"  ✗ Error: {data.get('error')}")
            bridge.stop()
            return False

        bridge.stop()

    except Exception as e:
        print(f"  ✗ Serial bridge error: {e}")
        return False

    # Test 2: Integration Layer
    print("\n[2/3] Testing integration layer...")
    try:
        from arduino_integration import initialize_arduino, get_arduino_temperature, is_arduino_available

        if initialize_arduino(port=port, baudrate=115200):
            print("  ✓ Integration initialized")

            time.sleep(2)

            if is_arduino_available():
                print("  ✓ Arduino available")
                data = get_arduino_temperature()
                print(f"  ✓ Temperature: {data.get('temperature_c')}°C")
            else:
                print("  ✗ Arduino not available")
                return False
        else:
            print("  ✗ Integration failed to initialize")
            return False

    except Exception as e:
        print(f"  ✗ Integration error: {e}")
        return False

    # Test 3: Telemetry Integration
    print("\n[3/3] Testing telemetry integration...")
    try:
        sys.path.insert(0, './Aqua_Scan/tilapiers')
        import telemetry

        if telemetry.ARDUINO_AVAILABLE:
            print("  ✓ Telemetry can access Arduino module")

            if telemetry.is_arduino_available():
                print("  ✓ Arduino available to telemetry")
                data = telemetry.get_arduino_temperature()
                print(f"  ✓ Temperature from telemetry: {data.get('temperature_c')}°C")
            else:
                print("  ✗ Arduino not available to telemetry")
                return False
        else:
            print("  ✗ ARDUINO_AVAILABLE = False in telemetry")
            return False

    except Exception as e:
        print(f"  ✗ Telemetry error: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "="*70)
    print("ALL TESTS PASSED! ✓")
    print("="*70)
    print("\nArduino is properly connected and integrated.")
    print("Temperature readings should appear on the dashboard without 'Simulated' badge.")
    print("\nMonitoring live readings (press Ctrl+C to stop)...")
    print("-"*70)

    try:
        while True:
            data = get_arduino_temperature()
            temp_c = data.get('temperature_c')
            temp_f = data.get('temperature_f')
            status = data.get('status')
            last = data.get('last_update', 'Never')

            print(f"\rTemp: {temp_c}°C ({temp_f}°F) | Status: {status} | Last: {last}", end='', flush=True)
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\nStopped.")
        from arduino_integration import stop_arduino
        stop_arduino()

    return True


if __name__ == '__main__':
    port = sys.argv[1] if len(sys.argv) > 1 else 'COM3'

    success = test_arduino_connection(port)

    if not success:
        print("\n" + "="*70)
        print("DIAGNOSTIC FAILED")
        print("="*70)
        print("\nTroubleshooting:")
        print("  1. Check Arduino is plugged in via USB")
        print("  2. Verify correct COM port (Device Manager on Windows)")
        print("  3. Close Arduino IDE Serial Monitor if open")
        print("  4. Check pyserial is installed: pip install pyserial")
        print("  5. Test standalone: python arduino_serial_bridge.py COM3")
        sys.exit(1)

    sys.exit(0)
