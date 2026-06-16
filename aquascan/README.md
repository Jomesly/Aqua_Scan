# AquaScan Backend

Local YOLOv8 backend for AquaScan fish health detection.

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

Train the wound/redness disease model longer:

```powershell
.\venv\Scripts\python.exe train_disease_model.py --dataset wound --epochs 25 --imgsz 640 --batch 8 --device cpu
```

## Important files

- `live_dashboard.py` - browser dashboard with webcam stream and calibration controls
- `detection_core.py` - shared model loading, camera startup, filtering, and metrics
- `model_config.py` - active model path and calibration presets
- `models/aquascan_disease_best.pt` - current dashboard model
- `models/aquascan_fish_best.pt` - fallback fish detector model
- `datasets/*.yaml` - dataset configs for training
