"""Synthetic sampling-board photos for tests: the real printable board, a dark
fish-shaped ellipse of known size, then a perspective warp like a hand-held phone."""

import cv2
import numpy as np

from tilapiers.vision import board_sheet


def board_photo(fish_len_cm=20.0, fish_h_cm=6.0, width_cm=38.0, height_cm=26.0, cover_marker=None,
                warp=True, blur=False):
    sheet = cv2.imdecode(np.frombuffer(board_sheet.render_png(width_cm, height_cm, dpi=72), np.uint8),
                         cv2.IMREAD_COLOR)
    geo = board_sheet.geometry(width_cm, height_cm, dpi=72)
    px = geo["px_per_cm"]
    x0, y0, x1, y1 = geo["inner_px"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    cv2.ellipse(sheet, (int(cx), int(cy)), (int(fish_len_cm * px / 2), int(fish_h_cm * px / 2)), 0, 0, 360,
                (70, 90, 110), -1)
    # tail fin, so the shape is fish-like
    tail_x = int(cx + fish_len_cm * px / 2)
    if cover_marker is not None:
        mx, my = geo["marker_px"][cover_marker]
        s = geo["marker_size_px"]
        cv2.rectangle(sheet, (int(mx) - 4, int(my) - 4), (int(mx + s) + 4, int(my + s) + 4), (230, 230, 230), -1)
    h, w = sheet.shape[:2]
    if warp:
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32([[40, 30], [w + 10, 0], [w - 20, h + 15], [10, h - 5]])
        M = cv2.getPerspectiveTransform(src, dst)
        sheet = cv2.warpPerspective(sheet, M, (w + 40, h + 40), borderValue=(90, 110, 90))
    sheet = (sheet.astype(np.float32) * 0.85).astype(np.uint8)  # camera exposure: paper is not pure white
    rng = np.random.default_rng(0)
    sheet = np.clip(sheet.astype(np.int16) + rng.integers(-6, 7, sheet.shape), 0, 255).astype(np.uint8)
    if blur:
        sheet = cv2.GaussianBlur(sheet, (31, 31), 12)
    _ = tail_x
    return sheet
