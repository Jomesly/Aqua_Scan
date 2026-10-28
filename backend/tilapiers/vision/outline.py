"""Fish outline, length and area on the flat-view board (paper Figure 10, step 6).

Length is the longest line across the outline (snout to tail-fin tip) and area is
the area inside it, both converted with the board scale. Until a YOLO
segmentation model is configured, the outline is found with classical image
processing (the fish against the plain board) and labeled "classical".
"""

import cv2
import numpy as np

EDGE_MARGIN_PX = 3


def _classical_mask(img, seed_box=None):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    h, w = lab.shape[:2]
    border = np.concatenate([lab[:6].reshape(-1, 3), lab[-6:].reshape(-1, 3),
                             lab[:, :6].reshape(-1, 3), lab[:, -6:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    dist = np.linalg.norm(lab - bg, axis=2)
    dist = cv2.GaussianBlur(dist, (5, 5), 0)
    d8 = np.clip(dist * (255.0 / max(dist.max(), 1e-6)), 0, 255).astype(np.uint8)
    _, mask = cv2.threshold(d8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if seed_box is not None:
        x1, y1, x2, y2 = (int(v) for v in seed_box)
        pad = int(0.08 * max(x2 - x1, y2 - y1))
        keep = np.zeros_like(mask)
        keep[max(0, y1 - pad):min(h, y2 + pad), max(0, x1 - pad):min(w, x2 + pad)] = 255
        mask = cv2.bitwise_and(mask, keep)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    return mask


def _seg_mask(img, seg_model):
    res = seg_model.predict(img, verbose=False)[0]
    if res.masks is None or not len(res.masks.xy):
        return None
    polys = sorted(res.masks.xy, key=lambda p: cv2.contourArea(p.astype(np.float32)), reverse=True)
    mask = np.zeros(img.shape[:2], np.uint8)
    cv2.fillPoly(mask, [polys[0].astype(np.int32)], 255)
    return mask


def measure(img, cm_per_px, seed_box=None, seg_model=None):
    method = "yolo-seg" if seg_model is not None else "classical"
    mask = _seg_mask(img, seg_model) if seg_model is not None else _classical_mask(img, seed_box)
    if mask is None:
        return {"ok": False, "method": method, "reasons": ["No fish outline found on the board."]}
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return {"ok": False, "method": method, "reasons": ["No fish outline found on the board."]}
    c = max(contours, key=cv2.contourArea)
    area_px = float(cv2.contourArea(c))
    h, w = img.shape[:2]
    if area_px < 0.002 * h * w:
        return {"ok": False, "method": method, "reasons": ["Fish outline too small: is the fish on the board?"]}
    hull = cv2.convexHull(c).reshape(-1, 2).astype(np.float64)
    d = np.linalg.norm(hull[:, None, :] - hull[None, :, :], axis=2)
    i, j = np.unravel_index(np.argmax(d), d.shape)
    x, y, bw, bh = cv2.boundingRect(c)
    touches = x <= EDGE_MARGIN_PX or y <= EDGE_MARGIN_PX or x + bw >= w - EDGE_MARGIN_PX or y + bh >= h - EDGE_MARGIN_PX
    reasons = ["Fish touches the board edge: the whole fish, including the tail fin, must be inside the markers."] \
        if touches else []
    return {"ok": not touches, "method": method, "length_cm": round(float(d[i, j]) * cm_per_px, 2),
            "area_cm2": round(area_px * cm_per_px ** 2, 2), "bbox": [x, y, x + bw, y + bh],
            "length_line": [hull[i].tolist(), hull[j].tolist()],
            "mask_poly": cv2.approxPolyDP(c, 1.5, True).reshape(-1, 2).tolist(),
            "touches_edge": touches, "reasons": reasons}
