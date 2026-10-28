"""Visible indicators measured from detected regions.

Color indices use a gray-world lighting correction until the color reference
card is detected; the correction method is reported with every result.
All indices are scaled to roughly 0-1 so regression coefficients are comparable.
"""

import numpy as np


def _crop(rgb, box):
    if box is None:
        return None
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    x0, x1 = max(0, min(x0, w - 1)), max(1, min(x1, w))
    y0, y1 = max(0, min(y0, h - 1)), max(1, min(y1, h))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    return rgb[y0:y1, x0:x1]


def gray_world(rgb):
    means = rgb.reshape(-1, 3).mean(axis=0)
    gain = means.mean() / np.maximum(means, 1e-6)
    return np.clip(rgb * gain, 0, 255)


def _redness(patch):
    if patch is None:
        return None
    r, g, b = (patch[..., i].mean() for i in range(3))
    total = r + g + b
    if total <= 0:
        return None
    # chromatic red share: 1/3 is neutral gray; map 0.33..0.55 -> 0..1
    return float(np.clip((r / total - 0.33) / 0.22, 0, 1))


def _clarity(patch):
    if patch is None:
        return None
    gray = patch @ np.asarray([0.299, 0.587, 0.114], dtype=np.float32)
    contrast = gray.std() / 64.0
    brightness = gray.mean() / 255.0
    return float(np.clip(0.6 * contrast + 0.4 * brightness, 0, 1))


def _skin_index(patch):
    """Higher = more even, normal coloration; discoloration lowers it."""
    if patch is None:
        return None
    hsv_like_sat = (patch.max(axis=-1) - patch.min(axis=-1)) / np.maximum(patch.max(axis=-1), 1)
    uneven = float(np.std(patch.mean(axis=-1)) / 80.0)
    return float(np.clip(1.0 - 0.6 * uneven - 0.4 * abs(float(hsv_like_sat.mean()) - 0.25), 0, 1))


def measure_indicators(rgb, detection):
    corrected = gray_world(rgb)
    regions = detection.regions or {}
    fish_box = detection.fish_box

    body_shape = None
    length_px = None
    if fish_box:
        x0, y0, x1, y1 = fish_box
        length_px = max(x1 - x0, y1 - y0)
        depth_px = min(x1 - x0, y1 - y0)
        body_shape = round(depth_px / length_px, 4) if length_px else None

    image_length_cm = None
    if length_px and detection.scale_px_per_cm:
        image_length_cm = round(length_px / detection.scale_px_per_cm, 2)

    def r(v):
        return round(v, 4) if v is not None else None

    return {
        "gill_color_index": r(_redness(_crop(corrected, regions.get("gill")))),
        "skin_color_index": r(_skin_index(_crop(corrected, fish_box))),
        "fin_integrity": r(min(detection.fin_area_ratio, 1.0)) if detection.fin_area_ratio is not None else None,
        "eye_clarity": r(_clarity(_crop(corrected, regions.get("eye")))),
        "body_shape": body_shape,
        "image_length_cm": image_length_cm,
        "lighting_correction": "gray-world (color card detection pending)",
    }
