"""Fish / region / reference-scale detector.

``YoloDetector`` loads trained YOLO26 segmentation weights through Ultralytics
when ``TILAPIERS_YOLO_WEIGHTS`` points at a file and ``ultralytics`` is
installed. Until the model is trained, ``StubDetector`` returns deterministic
placeholder regions so the rest of the pipeline can be exercised end to end.
Every result carries ``is_stub`` so stub output is never mistaken for a real
detection anywhere in the UI or the exports.
"""

import hashlib
import os
from dataclasses import asdict, dataclass, field

# Class names expected from the trained model (Chapter 3 annotation scheme).
CLASS_FISH = "fish"
CLASS_EYE = "eye"
CLASS_GILL = "gill"
CLASS_FIN = "fin"
CLASS_SCALE = "scale"

# Assumed real length of the printed reference scale on the board.
SCALE_LENGTH_CM = 10.0


@dataclass
class Detection:
    model: str
    is_stub: bool
    fish_box: tuple | None = None  # (x0, y0, x1, y1) in pixels of the analyzed image
    regions: dict = field(default_factory=dict)  # name -> box
    fin_area_ratio: float | None = None  # visible fin area / expected for length
    scale_px_per_cm: float | None = None
    confidence: float | None = None
    note: str | None = None

    def to_dict(self):
        return asdict(self)


class StubDetector:
    name = "stub (no trained YOLO26 weights)"
    is_stub = True

    def detect(self, rgb, image_bytes):
        h, w = rgb.shape[:2]
        seed = int(hashlib.sha1(image_bytes).hexdigest()[:8], 16)
        jitter = ((seed % 1000) / 1000.0 - 0.5) * 0.06
        x0, x1 = w * (0.12 + jitter), w * (0.88 + jitter)
        cy = h * 0.5
        depth = (x1 - x0) * 0.36
        y0, y1 = cy - depth / 2, cy + depth / 2
        L = x1 - x0
        regions = {
            CLASS_EYE: (x0 + 0.08 * L, cy - 0.10 * depth, x0 + 0.14 * L, cy - 0.10 * depth + 0.06 * L),
            CLASS_GILL: (x0 + 0.17 * L, cy - 0.25 * depth, x0 + 0.25 * L, cy + 0.20 * depth),
            CLASS_FIN: (x0 + 0.40 * L, y0 - 0.05 * depth, x0 + 0.70 * L, y0 + 0.15 * depth),
        }
        return Detection(
            model=self.name, is_stub=True,
            fish_box=(x0, y0, x1, y1), regions=regions,
            fin_area_ratio=round(0.78 + (seed % 200) / 1000.0, 3),
            scale_px_per_cm=w / 40.0,  # assumes the frame spans a 40 cm board
            confidence=None,
            note="Placeholder regions - train YOLO26 and set TILAPIERS_YOLO_WEIGHTS.",
        )


class YoloDetector:
    is_stub = False

    def __init__(self, weights):
        from ultralytics import YOLO  # optional dependency

        self._model = YOLO(weights)
        self.name = f"YOLO26 ({os.path.basename(weights)})"

    def detect(self, rgb, image_bytes):
        result = self._model.predict(rgb.astype("uint8"), verbose=False)[0]
        names = result.names
        best = {}
        for box, cls, conf in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist(), result.boxes.conf.tolist()):
            label = names[int(cls)]
            if label not in best or conf > best[label][1]:
                best[label] = (tuple(box), conf)
        fish = best.get(CLASS_FISH)
        scale = best.get(CLASS_SCALE)
        regions = {k: v[0] for k, v in best.items() if k in (CLASS_EYE, CLASS_GILL, CLASS_FIN)}
        px_per_cm = None
        if scale:
            sx0, sy0, sx1, sy1 = scale[0]
            px_per_cm = max(sx1 - sx0, sy1 - sy0) / SCALE_LENGTH_CM
        fin_ratio = None
        if CLASS_FIN in regions and fish:
            fx0, fy0, fx1, fy1 = regions[CLASS_FIN]
            bx0, by0, bx1, by1 = fish[0]
            fin_ratio = ((fx1 - fx0) * (fy1 - fy0)) / max((bx1 - bx0) * (by1 - by0) * 0.12, 1.0)
        return Detection(
            model=self.name, is_stub=False,
            fish_box=fish[0] if fish else None, regions=regions,
            fin_area_ratio=round(min(fin_ratio, 1.2), 3) if fin_ratio is not None else None,
            scale_px_per_cm=px_per_cm,
            confidence=round(fish[1], 3) if fish else None,
        )


def load_detector(weights_path=None):
    weights_path = weights_path or os.environ.get("TILAPIERS_YOLO_WEIGHTS")
    if weights_path and os.path.exists(weights_path):
        try:
            return YoloDetector(weights_path)
        except Exception as exc:  # ultralytics missing or bad weights
            print(f"[vision] Could not load YOLO weights ({exc}); using stub detector.")
    return StubDetector()
