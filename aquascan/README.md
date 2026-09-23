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

- `live_dashboard.py` - browser dashboard with webcam stream and calibration controls
- `detection_core.py` - shared model loading, camera startup, filtering, and metrics
- `model_config.py` - active model path and calibration presets
- `../weights/best.pt` - active trained model (Tilapia / pellets / waste)
