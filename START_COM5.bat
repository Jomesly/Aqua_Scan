@echo off
REM IMMEDIATE FIX - Connect Arduino on COM5 and restart dashboard

echo ============================================================
echo ARDUINO IS ON COM5 - CONNECTING NOW
echo ============================================================
echo.

cd /d C:\CodingProjects\Aqua_Scan\Aqua_Scan\tilapiers

echo [1/2] Testing Arduino on COM5...
echo.
timeout /t 2 /nobreak >nul

start "Arduino Test" cmd /c "venv\Scripts\python.exe test_com5.py"

echo Waiting 10 seconds to verify connection...
timeout /t 10 /nobreak >nul

echo.
echo [2/2] Starting dashboard with Arduino integration...
echo.
echo The dashboard will now auto-detect COM5
echo.
echo Look for this message:
echo   [Arduino] Connected SUCCESSFULLY on COM5
echo.
echo Then check:
echo   Arduino LCD: 18°C
echo   Dashboard:   18°C (should match!)
echo.

cd /d C:\CodingProjects\Aqua_Scan
npm run backend
