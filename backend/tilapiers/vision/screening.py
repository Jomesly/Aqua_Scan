"""Disease screening detector (paper YOLO26 Disease Screening module).

Loads any Ultralytics detect weights with the classes Healthy / Aeromonas / TiLV.
The study team's trained YOLOv8s is the default; YOLO26s weights drop in through
TILAPIERS_YOLO_WEIGHTS. If the weights cannot be loaded, the screener reports
itself unavailable. It never invents a class.
"""

import logging
import threading
from pathlib import Path

log = logging.getLogger(__name__)
EXPECTED = {"Healthy", "Aeromonas", "TiLV"}


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
        with self._lock:  # Ultralytics models are not thread-safe
            res = self._model.predict(img_bgr, conf=conf, imgsz=640, verbose=False)[0]
        out = []
        for box in res.boxes:
            out.append({"cls": self.names[int(box.cls)], "conf": round(float(box.conf), 4),
                        "box": [round(float(v), 1) for v in box.xyxy[0].tolist()]})
        return sorted(out, key=lambda d: d["conf"], reverse=True)

    def info(self):
        return {"name": self.name, "available": self.available, "error": self.error,
                "classes": list(self.names.values()), "path": str(self.path) if self.path else None}


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
