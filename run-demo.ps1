# Builds the frontend and starts Tilapiers in demo mode on http://127.0.0.1:8000
# Usage:  powershell -ExecutionPolicy Bypass -File .\run-demo.ps1
#         add -Reset to wipe the demo database and start fresh
param([switch]$Reset)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = "$root\backend\.venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host 'Creating Python environment (first run downloads PyTorch CPU, a few minutes)...'
    py -3.12 -m venv "$root\backend\.venv"
    & $py -m pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu
    & $py -m pip install -q -r "$root\backend\requirements.txt"
}
if (-not (Test-Path "$root\backend\models\yolov8s_best.pt")) {
    Write-Warning 'backend\models\yolov8s_best.pt not found: screening will show "model unavailable".'
}
if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host 'Installing frontend packages...'
    Push-Location "$root\frontend"; npm install --no-audit --no-fund; Pop-Location
}
Write-Host 'Building frontend...'
Push-Location "$root\frontend"; npx vite build; Pop-Location

if ($Reset -and (Test-Path "$root\backend\data\demo")) { Remove-Item -Recurse -Force "$root\backend\data\demo" }

$env:TILAPIERS_DEMO = '1'
$env:TILAPIERS_DATA_DIR = 'data/demo'
$env:TILAPIERS_SECRET_KEY = 'demo-only-secret-change-for-real-use'
$ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
       Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
       Select-Object -First 1).IPAddress
Write-Host ''
Write-Host 'Tilapiers demo:  http://127.0.0.1:8000'
if ($ip) { Write-Host "From a phone on the same Wi-Fi:  http://${ip}:8000" }
Write-Host 'Accounts: caretaker / caretaker123, technician / technician123, admin / admin123'
Write-Host '(Ctrl+C to stop)'
Push-Location "$root\backend"
& $py -m uvicorn tilapiers.main:app --host 0.0.0.0 --port 8000
Pop-Location
