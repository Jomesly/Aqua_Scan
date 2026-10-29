"""Per-photo and per-fish processing (paper Figures 4, 9 and 10).

quality check -> marker detection and flat-view correction -> outline (length,
area) -> crop -> disease screening -> annotated photo. In "no board" mode (public
or test photos) the marker step is skipped and length/area are not measured.
"""

import cv2

from ..rules.health import EROSION, NO_DEFECT, RED_SORES
from . import board, outline, quality

COLORS = {NO_DEFECT: (80, 160, 40), RED_SORES: (30, 30, 200), EROSION: (20, 120, 230)}


def _tag(img, text, x, y, color):
    """Text on a solid tag just above (x, y), or just below it at the top edge, so it reads on any photo."""
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    ty = y - 6 if y - th - base - 6 >= 0 else y + th + 8
    cv2.rectangle(img, (x, ty - th - 4), (x + tw + 8, ty + base), color, -1)
    cv2.putText(img, text, (x + 4, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)


def _result(ok, reasons, **kw):
    base = {"ok": ok, "reasons": reasons, "quality": None, "board": None, "outline": None, "detections": [],
            "top": None, "length_cm": None, "area_cm2": None, "annotated": False}
    base.update(kw)
    return base


def process_photo(img, board_mode, t, screener, seg_model, annotated_path):
    q = quality.assess(img)
    reasons = []
    if not q["ok"]:
        if board_mode:
            return _result(False, q["reasons"], quality=q)
        # The thresholds are set for board photos; a public/test photo is screened anyway, with a note.
        reasons = [f"Quality note: {r}" for r in q["reasons"]]

    work, cm_per_px, meas, crop_off = img, None, None, (0, 0)
    board_info = None
    if board_mode:
        b = board.detect(img, t.board_width_cm, t.board_height_cm)
        board_info = {"found": b["found"], "ok": b["ok"]}
        if not b["ok"]:
            return _result(False, b["reasons"], quality=q, board=board_info)
        work, cm_per_px = b["warped"], b["cm_per_px"]
        meas = outline.measure(work, cm_per_px, seg_model=seg_model)
        if not meas["ok"]:
            return _result(False, meas["reasons"], quality=q, board=board_info, outline=meas)

    crop = work
    if meas:
        x1, y1, x2, y2 = meas["bbox"]
        pad = int(0.06 * max(x2 - x1, y2 - y1))
        h, w = work.shape[:2]
        x1, y1, x2, y2 = max(0, x1 - pad), max(0, y1 - pad), min(w, x2 + pad), min(h, y2 + pad)
        crop, crop_off = work[y1:y2, x1:x2], (x1, y1)

    if not screener.available:
        dets = []
        reasons.append("Screening model unavailable: fish not screened.")
    else:
        dets = screener.predict(crop, t.det_conf)
        if not dets:
            reasons.append(f"No fish class above the detection threshold ({t.det_conf:.0%}): fish not screened.")
    # A defect box wins over a whole-fish "no visible defect" box in the same photo, as it does
    # across the two sides (paper Step 10): missing a defect is the costlier error.
    disease = [d for d in dets if d["cls"] != NO_DEFECT]
    best = max(disease or dets, key=lambda d: d["conf"]) if dets else None
    top = {"cls": best["cls"], "conf": best["conf"]} if best else None

    # Draw on a copy sized for the screen (long side 960-1280 px), so labels stay readable on small photos.
    long_side = max(work.shape[:2])
    s = 1280 / long_side if long_side > 1280 else 960 / long_side if long_side < 960 else 1.0
    vis = cv2.resize(work, (round(work.shape[1] * s), round(work.shape[0] * s)),
                     interpolation=cv2.INTER_CUBIC if s > 1 else cv2.INTER_AREA) if s != 1 else work.copy()
    if meas:
        import numpy as np

        cv2.polylines(vis, [np.int32(np.asarray(meas["mask_poly"]) * s)], True, (255, 220, 0), 2)
        p, q2 = (tuple(int(v * s) for v in pt) for pt in meas["length_line"])
        cv2.line(vis, p, q2, (0, 220, 255), 2)
        _tag(vis, f"L {meas['length_cm']:.1f} cm", p[0], p[1], (0, 150, 190))
    ox, oy = crop_off
    for d in sorted(dets, key=lambda d: d is best):
        x1, y1, x2, y2 = (int((v + o) * s) for v, o in zip(d["box"], (ox, oy, ox, oy)))
        color = COLORS.get(d["cls"], (200, 200, 200))
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 3 if d is best else 1)
        _tag(vis, f"{d['cls']} {d['conf']:.0%}", x1, y1, color)
    cv2.imwrite(str(annotated_path), vis, [cv2.IMWRITE_JPEG_QUALITY, 85])

    return _result(True, reasons, quality=q, board=board_info,
                   outline={k: meas[k] for k in ("method", "length_cm", "area_cm2", "bbox")} if meas else None,
                   detections=dets, top=top, annotated=True,
                   length_cm=meas["length_cm"] if meas else None, area_cm2=meas["area_cm2"] if meas else None)


def merge_sides(results):
    """Combine both photos of a fish (paper Figure 10, steps 6 and 10)."""
    good = [r for r in results if r and r.get("ok")]
    tops = [r["top"] for r in good if r.get("top")]
    disease = [x for x in tops if x["cls"] != NO_DEFECT]
    pick = max(disease or tops, key=lambda x: x["conf"]) if tops else None
    lengths = [r["length_cm"] for r in good if r.get("length_cm") is not None]
    areas = [r["area_cm2"] for r in good if r.get("area_cm2") is not None]
    return {"cls": pick["cls"] if pick else None, "conf": pick["conf"] if pick else None,
            "length_cm": round(sum(lengths) / len(lengths), 2) if lengths else None,
            "area_cm2": round(sum(areas) / len(areas), 2) if areas else None,
            "sides": len(good)}
