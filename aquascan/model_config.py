from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
MODEL_PATH = ROOT_DIR.parent / "weights" / "best.pt"
PERSON_MODEL_PATH = ROOT_DIR / "yolov8n.pt"

# best.pt classes: 0=Tilapia, 1=pellets, 2=waste. Live system tracks pellets only.
PELLETS_CLASS_ID = 1
DETECTION_CLASS_IDS = [PELLETS_CLASS_ID]
PERSON_CLASS_ID = 0
PERSON_CONFIDENCE_THRESHOLD = 0.35
PERSON_SUPPRESSION_IOU = 0.1
CONFIDENCE_THRESHOLD = 0.45
DETECT_IMGSZ = 512
PERSON_IMGSZ = 320
MAX_BOX_AREA_RATIO = 0.65
MIN_BOX_AREA_RATIO = 0.0005
MIN_BOX_ASPECT_RATIO = 0.2
MAX_BOX_ASPECT_RATIO = 5.0
CAMERA_INDICES = range(4)

# Pellets-only rules. conf_scale: effective conf = global_conf * conf_scale (clamped to [min_conf, max_conf]).
CLASS_CALIBRATION = {
    "pellets": {
        "conf_scale": 0.55,
        "min_conf": 0.18,
        "max_conf": 0.70,
        "min_box_area_ratio": 0.00002,
        "max_box_area_ratio": 0.08,
    },
}
DEFAULT_CLASS_RULE = {
    "conf_scale": 0.55,
    "min_conf": 0.18,
    "max_conf": 0.70,
    "min_box_area_ratio": 0.00002,
    "max_box_area_ratio": 0.08,
}

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
