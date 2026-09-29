
from ultralytics import YOLO
from model_config import MODEL_PATH

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

model = YOLO(str(MODEL_PATH))

print("Tilapiers model loaded")
print(f"Path: {MODEL_PATH}")
print(f"Classes: {model.names}")
