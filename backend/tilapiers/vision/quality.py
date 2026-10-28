"""Rule-based image-quality check for sampling-board photos.

Sharpness (variance of the Laplacian), exposure (mean brightness), and glare
(share of blown-out pixels) are measured directly from the photo. Presence of
the reference scale is decided by the detector and added by the pipeline.
"""

import numpy as np
from PIL import Image, ImageOps

MAX_SIDE = 1024

SHARPNESS_MIN = 60.0
BRIGHTNESS_MIN = 55.0
BRIGHTNESS_MAX = 205.0
GLARE_MAX_SHARE = 0.03


def load_rgb(path):
    img = Image.open(path)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    return np.asarray(img, dtype=np.float32)


def laplacian_variance(gray):
    lap = (
        -4 * gray[1:-1, 1:-1]
        + gray[:-2, 1:-1] + gray[2:, 1:-1]
        + gray[1:-1, :-2] + gray[1:-1, 2:]
    )
    return float(lap.var())


def check_quality(rgb):
    gray = rgb @ np.asarray([0.299, 0.587, 0.114], dtype=np.float32)
    sharp = laplacian_variance(gray)
    bright = float(gray.mean())
    glare = float(np.mean(np.all(rgb >= 250, axis=-1)))

    checks = [
        {"key": "sharpness", "label": "Sharpness", "value": round(sharp, 1),
         "passed": sharp >= SHARPNESS_MIN, "hint": "Hold the phone steady and tap to focus on the fish."},
        {"key": "exposure", "label": "Exposure", "value": round(bright, 1),
         "passed": BRIGHTNESS_MIN <= bright <= BRIGHTNESS_MAX,
         "hint": "Too dark - move out of deep shade." if bright < BRIGHTNESS_MIN else "Too bright - shade the board from direct sun."},
        {"key": "glare", "label": "Glare", "value": round(glare * 100, 2),
         "passed": glare <= GLARE_MAX_SHARE, "hint": "Tilt the phone or shade the board to remove reflections."},
    ]
    return checks
