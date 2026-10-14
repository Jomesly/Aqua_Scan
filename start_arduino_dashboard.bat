@echo off
REM Quick Start Script for Windows - Arduino Temperature Integration
REM Run this to start the dashboard with Arduino temperature sensor

echo ============================================================
echo Tilapiers Dashboard - Arduino Temperature Integration
echo ============================================================
echo.

REM Check if pyserial is installed
python -c "import serial" 2>nul
if errorlevel 1 (
    echo [!] Installing required Python package: pyserial
    pip install pyserial
    echo.
)

REM Set your Arduino COM port here
set ARDUINO_PORT=COM3

echo [*] Arduino Port: %ARDUINO_PORT%
echo [*] Change the ARDUINO_PORT variable in this file if needed
echo.

REM Test Arduino connection (optional)
echo [*] Testing Arduino connection...
timeout /t 2 /nobreak >nul

cd Aqua_Scan\tilapiers
python start_with_arduino.py

pause
