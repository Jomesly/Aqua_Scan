"""Marker detection and flat-view correction (paper Image-Quality Check, steps 2 and 4).

The four corner markers are found, a homography maps their inner corners to the
known board rectangle, and the corrected photo has a fixed scale of PX_PER_CM.
"""

import cv2
import numpy as np

from .board_sheet import DICT, INNER_CORNER

PX_PER_CM = 20.0
NAMES = {0: "top-left", 1: "top-right", 2: "bottom-right", 3: "bottom-left"}

_detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(DICT), cv2.aruco.DetectorParameters())


def detect(img_bgr, width_cm, height_cm):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = _detector.detectMarkers(gray)
    found = {}
    if ids is not None:
        for c, i in zip(corners, ids.flatten()):
            i = int(i)
            if i in INNER_CORNER and i not in found:
                found[i] = c.reshape(4, 2)[INNER_CORNER[i]]
    missing = [NAMES[i] for i in range(4) if i not in found]
    if missing:
        return {"found": sorted(found), "ok": False, "warped": None, "cm_per_px": None, "homography": None,
                "reasons": [f"Board marker missing: {', '.join(missing)}. Keep all four corner markers "
                            "uncovered and inside the frame."]}
    w, h = int(round(width_cm * PX_PER_CM)), int(round(height_cm * PX_PER_CM))
    src = np.float32([found[0], found[1], found[2], found[3]])
    dst = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    H = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img_bgr, H, (w, h))
    return {"found": [0, 1, 2, 3], "ok": True, "warped": warped, "cm_per_px": 1.0 / PX_PER_CM,
            "homography": H.tolist(), "corners_px": src.tolist(), "reasons": []}
