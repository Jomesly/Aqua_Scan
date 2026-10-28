# Builds the frontend and starts Tilapiers in demo mode on http://127.0.0.1:8000
# Usage:  powershell -ExecutionPolicy Bypass -File .\run-demo.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path "$root\backend\.venv")) {
    Write-Host 'Creating Python environment...'
    py -3.12 -m venv "$root\backend\.venv"
    & "$root\backend\.venv\Scripts\python.exe" -m pip install -q -r "$root\backend\requirements.txt"
}
if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host 'Installing frontend packages...'
    Push-Location "$root\frontend"; npm install --no-audit --no-fund; Pop-Location
}
Write-Host 'Building frontend...'
Push-Location "$root\frontend"; npx vite build; Pop-Location

$env:TILAPIERS_DEMO = '1'
$env:TILAPIERS_DATA_DIR = 'data/demo'
Write-Host 'Tilapiers demo: http://127.0.0.1:8000  (Ctrl+C to stop)'
Push-Location "$root\backend"
& .\.venv\Scripts\python.exe -m uvicorn tilapiers.main:app --host 0.0.0.0 --port 8000
Pop-Location
