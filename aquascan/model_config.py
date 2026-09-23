from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
MODEL_PATH = ROOT_DIR.parent / "weights" / "best.pt"
PERSON_MODEL_PATH = ROOT_DIR / "yolov8n.pt"

DETECTION_CLASS_IDS = None
PERSON_CLASS_ID = 0
PERSON_CONFIDENCE_THRESHOLD = 0.35
PERSON_SUPPRESSION_IOU = 0.1
CONFIDENCE_THRESHOLD = 0.45
MAX_BOX_AREA_RATIO = 0.65
MIN_BOX_AREA_RATIO = 0.0005
MIN_BOX_ASPECT_RATIO = 0.2
MAX_BOX_ASPECT_RATIO = 5.0
CAMERA_INDICES = range(4)

CALIBRATION_PRESETS = {
    "strict": {
        "confidence": 0.78,
        "min_box_area_ratio": 0.001,
        "max_box_area_ratio": 0.35,
    },
    "balanced": {
        "confidence": 0.45,
        "min_box_area_ratio": 0.0005,
        "max_box_area_ratio": 0.65,
    },
    "sensitive": {
        "confidence": 0.25,
        "min_box_area_ratio": 0.0001,
        "max_box_area_ratio": 0.85,
    },
}
