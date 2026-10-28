"""Rule-based image-quality check (paper Image-Quality Check, step 3).

Sharpness (variance of the Laplacian), exposure (mean brightness) and glare
(share of blown-out pixels) are measured from the photo. The thresholds are
starting values to be set on the pilot photos at the study site.
"""

import cv2
import numpy as np

MAX_SIDE = 1024
SHARPNESS_MIN = 60.0
BRIGHTNESS_MIN = 50.0
BRIGHTNESS_MAX = 215.0
GLARE_MAX_SHARE = 0.08


def load(path_or_bytes):
    """Read a photo as BGR, honoring EXIF orientation (phones store it rotated)."""
    from PIL import Image, ImageOps
    import io

    src = io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, (bytes, bytearray)) else path_or_bytes
    img = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


def assess(img_bgr):
    h, w = img_bgr.shape[:2]
    scale = MAX_SIDE / max(h, w)
    small = cv2.resize(img_bgr, (int(w * scale), int(h * scale))) if scale < 1 else img_bgr
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    bright = float(gray.mean())
    glare = float(np.mean(np.all(small >= 250, axis=-1)))
    reasons = []
    if sharp < SHARPNESS_MIN:
        reasons.append("Photo is blurry: hold the phone steady on the stand and tap to focus on the fish.")
    if bright < BRIGHTNESS_MIN:
        reasons.append("Photo is too dark: move out of deep shade.")
    elif bright > BRIGHTNESS_MAX:
        reasons.append("Photo is too bright: shade the board from direct sun.")
    if glare > GLARE_MAX_SHARE:
        reasons.append("Strong glare on the board: tilt or shade it to remove reflections.")
    return {"ok": not reasons, "sharpness": round(sharp, 1), "brightness": round(bright, 1),
            "glare_share": round(glare, 4), "reasons": reasons}
