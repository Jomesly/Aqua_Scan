@echo off
REM Complete Arduino Integration Test Suite for Windows

echo ============================================================
echo ARDUINO TEMPERATURE INTEGRATION - VERIFICATION SUITE
echo ============================================================
echo.

REM Step 1: Check if Arduino code is uploaded
echo [STEP 1/5] Checking Arduino Setup
echo --------------------------------------------------------
echo.
echo Please verify:
echo   [?] Arduino is connected via USB
echo   [?] arduino_temp_sensor.ino is uploaded to Arduino
echo   [?] Arduino LCD shows temperature (if connected)
echo.
set /p arduino_ready="Is Arduino ready? (y/n): "
if /i not "%arduino_ready%"=="y" (
    echo.
    echo Please complete Arduino setup first:
    echo   1. Open arduino_temp_sensor.ino in Arduino IDE
    echo   2. Install libraries: OneWire, DallasTemperature, LiquidCrystal_I2C, ArduinoJson
    echo   3. Upload to Arduino
    echo   4. Check LCD shows temperature
    echo.
    pause
    exit /b 1
)

REM Step 2: Install Python dependencies
echo.
echo [STEP 2/5] Installing Python Dependencies
echo --------------------------------------------------------
python -c "import serial" 2>nul
if errorlevel 1 (
    echo Installing pyserial...
    pip install pyserial
    if errorlevel 1 (
        echo ERROR: Failed to install pyserial
        pause
        exit /b 1
    )
    echo   [OK] pyserial installed
) else (
    echo   [OK] pyserial already installed
)

REM Step 3: Test Arduino standalone
echo.
echo [STEP 3/5] Testing Arduino Connection
echo --------------------------------------------------------
echo.
set /p arduino_port="Enter your Arduino COM port (e.g., COM3): "
echo.
echo Testing connection on %arduino_port%...
timeout /t 2 /nobreak >nul
python test_arduino_connection.py %arduino_port%
if errorlevel 1 (
    echo.
    echo ERROR: Arduino connection test failed
    echo.
    echo Common issues:
    echo   - Wrong COM port (check Device Manager)
    echo   - Arduino IDE Serial Monitor is open (close it)
    echo   - USB cable not connected
    echo   - Driver issues
    echo.
    pause
    exit /b 1
)

REM Step 4: Start the dashboard server
echo.
echo [STEP 4/5] Starting Dashboard Server
echo --------------------------------------------------------
echo.
echo The dashboard server will start with Arduino integration.
echo Wait for the server to fully start, then we'll test the web interface.
echo.
echo Starting in 3 seconds...
timeout /t 3 /nobreak >nul

REM Update the port in the startup script
powershell -Command "(Get-Content 'Aqua_Scan\tilapiers\start_with_arduino.py') -replace \"ARDUINO_PORT = '[^']*'\", \"ARDUINO_PORT = '%arduino_port%'\" | Set-Content 'Aqua_Scan\tilapiers\start_with_arduino.py'"

start "Tilapiers Dashboard" cmd /k "cd Aqua_Scan\tilapiers && python start_with_arduino.py"

echo.
echo Waiting for server to start (10 seconds)...
timeout /t 10 /nobreak >nul

REM Step 5: Test web integration
echo.
echo [STEP 5/5] Testing Web Dashboard Integration
echo --------------------------------------------------------
echo.
python test_web_integration.py
if errorlevel 1 (
    echo.
    echo ERROR: Web integration test failed
    echo.
    echo The Arduino is connected but not integrated with the dashboard.
    echo Check the dashboard console for error messages.
    echo.
    pause
    exit /b 1
)

REM Success!
echo.
echo ============================================================
echo SUCCESS! Your Arduino is connected to the dashboard!
echo ============================================================
echo.
echo What to check:
echo   1. Open http://127.0.0.1:8000 in your browser
echo   2. Look at "Environmental Parameters" section
echo   3. Temperature should update every 2 seconds
echo   4. NO "Simulated" badge should appear
echo   5. Temperature should match your Arduino LCD display
echo.
echo Endpoints to verify:
echo   - Dashboard:       http://127.0.0.1:8000
echo   - Environment API: http://127.0.0.1:8000/api/environment
echo   - Arduino Status:  http://127.0.0.1:8000/api/arduino/status
echo.
echo Press any key to open the dashboard in your browser...
pause >nul
start http://127.0.0.1:8000
echo.
echo Dashboard is running. Close the dashboard window to stop.
echo.
