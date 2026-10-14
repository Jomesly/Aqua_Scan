#!/usr/bin/env python3
"""
Simple test to verify Arduino temperature is flowing to the web dashboard
"""

import requests
import time
import sys

def test_web_integration():
    """Test that Arduino temperature appears in the web API"""

    print("\n" + "="*70)
    print("TESTING ARDUINO → WEB DASHBOARD INTEGRATION")
    print("="*70)

    base_url = "http://127.0.0.1:8000"

    # Test 1: Check if server is running
    print("\n[1/3] Checking if dashboard server is running...")
    try:
        response = requests.get(f"{base_url}/api/status", timeout=2)
        if response.status_code == 200:
            print(f"  ✓ Dashboard server is running")
        else:
            print(f"  ✗ Server returned status {response.status_code}")
            return False
    except requests.ConnectionError:
        print(f"  ✗ Cannot connect to {base_url}")
        print(f"  → Start the server first: python Aqua_Scan/tilapiers/live_dashboard.py")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

    # Test 2: Check Arduino status endpoint
    print("\n[2/3] Checking Arduino status endpoint...")
    try:
        response = requests.get(f"{base_url}/api/arduino/status", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"  Status: {data.get('status')}")
            print(f"  Available: {data.get('arduino_available')}")
            print(f"  Temperature: {data.get('temperature_c')}°C")
            print(f"  Last Update: {data.get('last_update')}")

            if data.get('status') == 'connected':
                print(f"  ✓ Arduino is connected")
            else:
                print(f"  ✗ Arduino status: {data.get('status')}")
                print(f"  ✗ Error: {data.get('error')}")
                return False
        else:
            print(f"  ✗ Status endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

    # Test 3: Check environment endpoint (what the dashboard uses)
    print("\n[3/3] Checking environment endpoint (dashboard data)...")
    try:
        response = requests.get(f"{base_url}/api/environment", timeout=2)
        if response.status_code == 200:
            data = response.json()
            temp = data.get('temperature_c')
            simulated = data.get('simulated')

            print(f"  Temperature: {temp}°C")
            print(f"  Simulated: {simulated}")

            if simulated == False:
                print(f"  ✓ Temperature is from Arduino (not simulated)")
            else:
                print(f"  ✗ Temperature is still simulated")
                print(f"  → Arduino may not be connected or initialized")
                return False
        else:
            print(f"  ✗ Environment endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

    print("\n" + "="*70)
    print("ALL TESTS PASSED! ✓")
    print("="*70)
    print("\nArduino temperature is successfully flowing to the web dashboard!")
    print("Dashboard URL: http://127.0.0.1:8000")
    print("\nMonitoring live updates (press Ctrl+C to stop)...")
    print("-"*70)

    try:
        while True:
            response = requests.get(f"{base_url}/api/environment", timeout=2)
            data = response.json()
            temp = data.get('temperature_c')
            simulated = data.get('simulated')
            gate = data.get('gate_state')

            sim_badge = "🟡 SIMULATED" if simulated else "✓ REAL"
            gate_badge = "✓ SAFE" if gate == "Safe" else "✗ UNSAFE"

            print(f"\r  Temp: {temp}°C | {sim_badge} | Gate: {gate_badge}  ", end='', flush=True)
            time.sleep(2)

    except KeyboardInterrupt:
        print("\n\nStopped.")

    return True


if __name__ == '__main__':
    success = test_web_integration()

    if not success:
        print("\n" + "="*70)
        print("INTEGRATION TEST FAILED")
        print("="*70)
        print("\nThe Arduino is not connected to the web dashboard.")
        print("\nTroubleshooting steps:")
        print("  1. Make sure Arduino is connected: python test_arduino_connection.py COM3")
        print("  2. Restart the dashboard server to reinitialize Arduino")
        print("  3. Check console output for Arduino initialization messages")
        print("  4. Test Arduino status: curl http://127.0.0.1:8000/api/arduino/status")
        sys.exit(1)

    sys.exit(0)
