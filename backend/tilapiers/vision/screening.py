"""Disease screening detector (paper YOLO26 Disease Screening module).

Loads any Ultralytics detect weights trained with the classes Healthy / Aeromonas / TiLV.
The study team's trained YOLOv8s is the default; YOLO26s weights drop in through
TILAPIERS_YOLO_WEIGHTS. If the weights cannot be loaded, the screener reports
itself unavailable. It never invents a class.

The app flags visible defects; it does not name diseases. The training labels are
translated here, once, so everything after the model sees only defect names.
"""

import logging
import threading
from pathlib import Path

import cv2

from ..rules.health import EROSION, NO_DEFECT, RED_SORES

log = logging.getLogger(__name__)
# Training label -> visible defect shown in the app.
DEFECT_OF_LABEL = {"Healthy": NO_DEFECT, "TiLV": EROSION, "Aeromonas": RED_SORES}
EXPECTED = set(DEFECT_OF_LABEL)
# Roboflow exports stretch every training image to 640x640 (no letterbox) by default, so photos are
# stretched the same way before screening. On public Aeromonas/TiLV photos this found more fish and
# stopped defects on long, thin photos from being missed.
IMGSZ = 640


class Screener:
    def __init__(self, weights_path):
        self.path = Path(weights_path) if weights_path else None
        self.available = False
        self.name = self.path.stem if self.path else "none"
        self.error = None
        self.names = {}
        self._model = None
        self._lock = threading.Lock()
        if not self.path or not self.path.exists():
            self.error = f"Weights not found: {self.path}"
            return
        try:
            from ultralytics import YOLO

            self._model = YOLO(str(self.path))
            self.names = dict(self._model.names)
            missing = EXPECTED - set(self.names.values())
            if missing:
                self.error = f"Model classes {sorted(self.names.values())} do not include {sorted(missing)}"
                return
            self.available = True
        except Exception as exc:  # pragma: no cover - depends on the local install
            log.exception("Could not load screening model")
            self.error = f"Could not load model: {exc}"

    def predict(self, img_bgr, conf):
        if not self.available:
            return []
        h, w = img_bgr.shape[:2]
        square = cv2.resize(img_bgr, (IMGSZ, IMGSZ))
        with self._lock:  # Ultralytics models are not thread-safe
            res = self._model.predict(square, conf=conf, imgsz=IMGSZ, verbose=False)[0]
        sx, sy = w / IMGSZ, h / IMGSZ
        out = []
        for box in res.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            out.append({"cls": DEFECT_OF_LABEL[self.names[int(box.cls)]], "conf": round(float(box.conf), 4),
                        "box": [round(x1 * sx, 1), round(y1 * sy, 1), round(x2 * sx, 1), round(y2 * sy, 1)]})
        return sorted(out, key=lambda d: d["conf"], reverse=True)

    def info(self):
        return {"name": self.name, "available": self.available, "error": self.error,
                "classes": [DEFECT_OF_LABEL.get(n, n) for n in self.names.values()], "path": str(self.path) if self.path else None}


def load_seg(weights_path):
    """Optional YOLO segmentation model for the fish outline."""
    if not weights_path or not Path(weights_path).exists():
        return None
    try:
        from ultralytics import YOLO

        return YOLO(str(weights_path))
    except Exception:  # pragma: no cover
        log.exception("Could not load segmentation model")
        return None
