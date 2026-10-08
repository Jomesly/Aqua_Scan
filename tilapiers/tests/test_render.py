import cv2
import numpy as np

from detection_core import (
    Calibration,
    LARGE_LABEL_BOX_PX,
    LARGE_LABEL_FONT,
    SMALL_LABEL_FONT,
    annotate_frame,
    draw_detections,
    label_style,
    result_metrics,
)


class _Arr(list):
    def tolist(self):
        def convert(value):
            if isinstance(value, (list, tuple, _Arr)):
                return [convert(item) for item in value]
            return value

        return convert(list(self))


class _Pred:
    def __init__(self, class_id, confidence, cx, cy, w, h):
        self.cls = [class_id]
        self.conf = [confidence]
        self.xyxy = _Arr([_Arr([cx - w, cy - h, cx + w, cy + h])])
        self.xyxyxyxy = _Arr(
            [
                _Arr(
                    [
                        _Arr([cx - w, cy - h]),
                        _Arr([cx + w, cy - h]),
                        _Arr([cx + w, cy + h]),
                        _Arr([cx - w, cy + h]),
                    ]
                )
            ]
        )


class _Result:
    def __init__(self, preds):
        self.names = {0: "Bubbles", 1: "Pellets", 2: "Tilapia", 3: "Waste"}
        self.obb = preds
        self.boxes = None


CALIBRATION = Calibration(
    confidence=0.45,
    max_box_area_ratio=0.65,
    min_box_area_ratio=0.0005,
    min_box_aspect_ratio=0.2,
    max_box_aspect_ratio=5.0,
)


def _long_flat_run(frame):
    """Longest run of lit pixels in a single row.

    A filled label chip is ~100 px wide; a pellet outline is only a few pixels.
    """
    lit = (frame.max(axis=2) > 0).astype(np.uint8)
    best = 0
    for row in lit:
        run = 0
        for value in row:
            run = run + 1 if value else 0
            best = max(best, run)
    return best


def test_label_style_switches_at_the_readable_box_boundary():
    assert SMALL_LABEL_FONT < LARGE_LABEL_FONT
    assert LARGE_LABEL_BOX_PX >= 16

    large = label_style(LARGE_LABEL_BOX_PX, LARGE_LABEL_BOX_PX)
    small = label_style(LARGE_LABEL_BOX_PX - 1, LARGE_LABEL_BOX_PX - 1)
    pellet = label_style(8, 8)

    assert large[0] == LARGE_LABEL_FONT
    assert large[1] == 2
    assert small[0] == SMALL_LABEL_FONT
    assert pellet[0] == SMALL_LABEL_FONT
    assert pellet[0] < 0.4


def test_pellets_are_still_labelled_with_the_small_font():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    preds = [
        _Pred(1, 0.7, (i * 37) % 600 + 20, (i * 53) % 440 + 20, 4, 4)
        for i in range(40)
    ]
    out = draw_detections(frame.copy(), _Result(preds))

    assert not np.array_equal(out, frame), "pellet outlines should be drawn"
    assert _long_flat_run(out) >= 40, "pellets must still carry a label chip"


def test_fish_keep_the_larger_label():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    preds = [_Pred(2, 0.8, 320, 240, 45, 30)]
    out = draw_detections(frame.copy(), _Result(preds))

    assert _long_flat_run(out) >= LARGE_LABEL_BOX_PX, "readable boxes keep the big label"


def test_annotate_frame_never_mutates_the_source_frame():
    frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
    original = frame.copy()
    preds = [_Pred(2, 0.8, 160, 120, 45, 30), _Pred(1, 0.7, 40, 40, 4, 4)]

    annotated, metrics = annotate_frame(frame, _Result(preds), CALIBRATION)

    assert np.array_equal(frame, original)
    assert annotated.shape == frame.shape
    assert metrics["pellet_count"] == 1
    assert metrics["count"] == 2


def test_precomputed_metrics_are_reused_for_the_overlay_header():
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    result = _Result([_Pred(1, 0.7, 40, 40, 4, 4)])
    metrics = dict(result_metrics(result))
    metrics["class_counts"] = {"Pellets": 99}
    metrics["count"] = 99

    _, used = annotate_frame(frame, result, CALIBRATION, metrics)

    assert used["count"] == 99
    assert used["class_counts"]["Pellets"] == 99


def test_only_the_pellets_class_is_counted():
    result = _Result(
        [
            _Pred(1, 0.7, 40, 40, 4, 4),
            _Pred(1, 0.7, 60, 60, 4, 4),
            _Pred(2, 0.8, 160, 120, 45, 30),
            _Pred(3, 0.6, 200, 150, 10, 10),
        ]
    )
    metrics = result_metrics(result)

    assert metrics["pellet_count"] == 2
    assert metrics["count"] == 4
    assert metrics["class_counts"] == {"Pellets": 2, "Tilapia": 1, "Waste": 1}


def test_annotation_stays_within_a_budget_for_a_heavy_frame():
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    preds = [_Pred(2, 0.8, (i * 31) % 1200 + 40, (i * 17) % 640 + 40, 45, 30)
             for i in range(40)]
    preds += [_Pred(1, 0.7, (i * 53) % 1270 + 5, (i * 37) % 710 + 5, 4, 4)
              for i in range(300)]
    result = _Result(preds)
    metrics = result_metrics(result)

    best = float("inf")
    for _ in range(5):
        start = cv2.getTickCount()
        annotated, _ = annotate_frame(frame, result, CALIBRATION, metrics)
        cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
        best = min(best, (cv2.getTickCount() - start) / cv2.getTickFrequency())

    assert metrics["count"] == 340
    assert best < 0.15, f"heavy frame took {best*1000:.0f} ms, budget is 150 ms"
