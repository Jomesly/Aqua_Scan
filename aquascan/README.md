# Tilapiers Backend

Local YOLOv8 backend for Tilapiers feed-pellet and tank monitoring.

## Main commands

Run the live dashboard:

```powershell
.\venv\Scripts\python.exe -m uvicorn live_dashboard:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

Test the active model:

```powershell
.\venv\Scripts\python.exe check_model.py
```

## Important files

- `live_dashboard.py` - browser dashboard with webcam stream, camera source settings, and calibration controls
- `detection_core.py` - shared model loading, camera startup, filtering, and metrics
- `model_config.py` - active model path and calibration presets
- `../weights/best.pt` - active trained model (Tilapia / pellets / waste)

## Camera settings

On the live dashboard, open **Settings - camera source**:

- **Stop camera / Start camera** - stop fully releases the webcam and blacks out the feed. On start, cameras are scanned: if only one is found the feed starts immediately; if multiple are found a dropdown lets you choose before starting (0 found starts Auto)
- **Auto** - first available webcam
- **Camera 0-7** - pick a device index
- **Custom source** - camera index or `rtsp://` / `http(s)://` URL
- **Scan available cameras** - probes local webcams via `GET /api/cameras`
- **Apply camera** - posts to `POST /api/camera` and switches the live stream without restarting the server
- **Power** - `POST /api/camera/power` with `{"enabled": false}` stops the camera; `{"enabled": true}` resumes
