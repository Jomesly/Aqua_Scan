"""Printable sampling board: four ArUco markers (DICT_4X4_50, ids 0-3) whose inner
corners mark the measurement rectangle of known size (paper Figure 12).

    id 0 ┌──────────────┐ id 1        Each marker sits outside the rectangle; the
         │   place the   │             corner of the marker that touches the
         │   fish here   │             rectangle is the reference point.
    id 3 └──────────────┘ id 2
"""

import io

import cv2
import numpy as np
from PIL import Image

DICT = cv2.aruco.DICT_4X4_50
MARKER_CM = 3.0
QUIET_CM = 0.6  # white border around each marker so it can be detected
# ArUco returns marker corners as TL, TR, BR, BL. Index of the corner touching the rectangle:
INNER_CORNER = {0: 2, 1: 3, 2: 0, 3: 1}


def geometry(width_cm, height_cm, dpi=150):
    px = dpi / 2.54
    edge = MARKER_CM + QUIET_CM
    page_w, page_h = width_cm + 2 * edge, height_cm + 2 * edge
    x0, y0 = edge * px, edge * px
    x1, y1 = x0 + width_cm * px, y0 + height_cm * px
    s = MARKER_CM * px
    return {
        "px_per_cm": px,
        "page_cm": (page_w, page_h),
        "page_px": (int(round(page_w * px)), int(round(page_h * px))),
        "inner_px": (x0, y0, x1, y1),
        "marker_size_px": s,
        # top-left pixel of each marker
        "marker_px": {0: (x0 - s, y0 - s), 1: (x1, y0 - s), 2: (x1, y1), 3: (x0 - s, y1)},
    }


def _sheet(width_cm, height_cm, dpi):
    g = geometry(width_cm, height_cm, dpi)
    w, h = g["page_px"]
    img = np.full((h, w), 255, np.uint8)
    s = int(round(g["marker_size_px"]))
    aruco = cv2.aruco.getPredefinedDictionary(DICT)
    for mid, (mx, my) in g["marker_px"].items():
        marker = cv2.aruco.generateImageMarker(aruco, mid, s)
        x, y = int(round(mx)), int(round(my))
        img[y:y + s, x:x + s] = marker
    x0, y0, x1, y1 = (int(round(v)) for v in g["inner_px"])
    cv2.rectangle(img, (x0, y0), (x1, y1), 200, max(1, int(dpi / 150)))
    scale = dpi / 150
    cv2.putText(img, f"Tilapiers sampling board - inner {width_cm:g} x {height_cm:g} cm - print at 100% scale",
                (x0 + int(10 * scale), y1 - int(12 * scale)), cv2.FONT_HERSHEY_SIMPLEX, 0.45 * scale, 160,
                max(1, int(scale)), cv2.LINE_AA)
    return img


def render_png(width_cm, height_cm, dpi=150):
    ok, buf = cv2.imencode(".png", _sheet(width_cm, height_cm, dpi))
    return buf.tobytes()


def render_pdf(width_cm, height_cm, dpi=200):
    """PDF at true physical size (print at 100 %, no 'fit to page')."""
    out = io.BytesIO()
    Image.fromarray(_sheet(width_cm, height_cm, dpi)).save(out, format="PDF", resolution=dpi)
    return out.getvalue()
