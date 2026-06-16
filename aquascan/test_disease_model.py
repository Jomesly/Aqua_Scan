from pathlib import Path

import cv2

from detection_core import Calibration, detect_fish, load_model, result_metrics


ROOT_DIR = Path(__file__).resolve().parent
TEST_DIR = ROOT_DIR.parent / "fish disease detection.v7i.yolov8" / "test" / "images"


model = load_model()
calibration = Calibration(confidence=0.25, max_box_area_ratio=0.9, min_box_area_ratio=0.0)

image_paths = sorted(TEST_DIR.glob("*.*"))[:20]
if not image_paths:
    raise FileNotFoundError(f"No test images found: {TEST_DIR}")

print(f"Model classes: {model.names}")
hits = 0
total = 0
best_confidence = 0.0

for image_path in image_paths:
    frame = cv2.imread(str(image_path))
    if frame is None:
        continue

    result = detect_fish(frame, model, calibration)
    metrics = result_metrics(result)
    hits += 1 if metrics["count"] else 0
    total += metrics["count"]
    best_confidence = max(best_confidence, metrics["max_confidence"])
    print(f"{image_path.name}: detections={metrics['count']} max_conf={metrics['max_confidence']:.2f}")

print(f"Hit images: {hits}/{len(image_paths)}")
print(f"Total detections: {total}")
print(f"Best confidence: {best_confidence:.2f}")
