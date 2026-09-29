import time

import cv2
from ultralytics import YOLO

from model_config import (
    CAMERA_INDICES,
    CALIBRATION_PRESETS,
    CLASS_CALIBRATION,
    CLASS_COLORS,
    CONFIDENCE_THRESHOLD,
    DEFAULT_BOX_COLOR,
    DEFAULT_CLASS_RULE,
    DETECT_IMGSZ,
    DETECTION_CLASS_IDS,
    MAX_BOX_AREA_RATIO,
    MAX_BOX_ASPECT_RATIO,
    MIN_BOX_AREA_RATIO,
    MIN_BOX_ASPECT_RATIO,
    MODEL_PATH,
    PERSON_CLASS_ID,
    PERSON_CONFIDENCE_THRESHOLD,
    PERSON_IMGSZ,
    PERSON_MODEL_PATH,
    PERSON_SUPPRESSION_IOU,
)


class Calibration:
    def __init__(
        self,
        confidence=CONFIDENCE_THRESHOLD,
        max_box_area_ratio=MAX_BOX_AREA_RATIO,
        min_box_area_ratio=MIN_BOX_AREA_RATIO,
        min_box_aspect_ratio=MIN_BOX_ASPECT_RATIO,
        max_box_aspect_ratio=MAX_BOX_ASPECT_RATIO,
    ):
        self.confidence = confidence
        self.max_box_area_ratio = max_box_area_ratio
        self.min_box_area_ratio = min_box_area_ratio
        self.min_box_aspect_ratio = min_box_aspect_ratio
        self.max_box_aspect_ratio = max_box_aspect_ratio

    def as_dict(self):
        return {
            "confidence": self.confidence,
            "max_box_area_ratio": self.max_box_area_ratio,
            "min_box_area_ratio": self.min_box_area_ratio,
            "min_box_aspect_ratio": self.min_box_aspect_ratio,
            "max_box_aspect_ratio": self.max_box_aspect_ratio,
        }

    def apply_preset(self, name):
        preset = CALIBRATION_PRESETS.get(name)
        if not preset:
            raise ValueError(f"Unknown calibration preset: {name}")

        self.confidence = preset["confidence"]
        self.min_box_area_ratio = preset["min_box_area_ratio"]
        self.max_box_area_ratio = preset["max_box_area_ratio"]


def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
    return YOLO(str(MODEL_PATH))


def load_person_model():
    if not PERSON_MODEL_PATH.exists():
        return None
    return YOLO(str(PERSON_MODEL_PATH))


def open_camera(index=None):
    indices = [index] if index is not None else list(CAMERA_INDICES)

    for device_index in indices:
        if isinstance(device_index, str) and device_index.startswith(("http://", "https://", "rtsp://")):
            cap = cv2.VideoCapture(device_index)
            if cap.isOpened() and cap.read()[0]:
                print(f"Using stream {device_index}")
                return cap
            cap.release()
            continue

        cap = cv2.VideoCapture(int(device_index), cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            continue

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        for _ in range(10):
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"Using webcam index {device_index}")
                return cap

        cap.release()

    return None


def parse_camera_source(source):
    if source is None or source == "" or source == "auto":
        return None

    if isinstance(source, int):
        return source

    text = str(source).strip()
    if text.lower() == "auto":
        return None
    if text.isdigit():
        return int(text)
    return text


_camera_names_cache = {"names": {}, "at": 0.0}
_CAMERA_NAMES_TTL = 4.0


def enumerate_camera_names(force_refresh=False):
    now = time.monotonic()
    if not force_refresh and now - _camera_names_cache["at"] < _CAMERA_NAMES_TTL:
        return dict(_camera_names_cache["names"])

    names = {}
    try:
        from pygrabber.dshow_graph import FilterGraph

        for index, name in enumerate(FilterGraph().get_input_devices()):
            label = str(name).strip() or f"Camera {index}"
            names[index] = label
    except Exception as exc:
        # Do not cache a failed scan, otherwise one bad call blanks the list.
        print(f"Camera enumeration failed ({type(exc).__name__}: {exc})", flush=True)
        return dict(_camera_names_cache["names"]) if _camera_names_cache["at"] else {}

    if not names:
        return dict(_camera_names_cache["names"]) if _camera_names_cache["at"] else {}

    _camera_names_cache["names"] = names
    _camera_names_cache["at"] = now
    return dict(names)


def list_cameras():
    names = enumerate_camera_names(force_refresh=True)
    if names:
        return [
            {"index": index, "label": name, "source": str(index)}
            for index, name in names.items()
        ]

    found = []
    for index in range(8):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            continue

        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            found.append({"index": index, "label": f"Camera {index}", "source": str(index)})

    return found


def class_rule(class_name):
    return CLASS_CALIBRATION.get(class_name, DEFAULT_CLASS_RULE)


def class_confidence(class_name, calibration):
    rule = class_rule(class_name)
    conf = calibration.confidence * rule.get("conf_scale", 1.0)
    return min(max(conf, rule.get("min_conf", 0.15)), rule.get("max_conf", 0.99))


def inference_confidence(calibration):
    """Lowest per-class conf so YOLO returns candidates for every class."""
    confs = [class_confidence(name, calibration) for name in CLASS_CALIBRATION]
    confs.append(calibration.confidence)
    return min(confs)


def filter_result(result, frame_shape, calibration):
    frame_area = frame_shape[0] * frame_shape[1]
    keep = []

    for index, box in enumerate(result.boxes):
        class_id = int(box.cls[0])
        class_name = result.names.get(class_id, str(class_id))
        conf = float(box.conf[0])

        if class_name not in CLASS_CALIBRATION:
            continue

        rule = class_rule(class_name)

        if conf < class_confidence(class_name, calibration):
            continue

        x1, y1, x2, y2 = box.xyxy[0].tolist()
        width = max(x2 - x1, 1)
        height = max(y2 - y1, 1)
        area_ratio = (width * height) / frame_area
        aspect_ratio = width / height

        min_area = rule.get("min_box_area_ratio")
        if min_area is None:
            min_area = calibration.min_box_area_ratio
        max_area = rule.get("max_box_area_ratio")
        if max_area is None:
            max_area = calibration.max_box_area_ratio

        if area_ratio < min_area:
            continue
        if area_ratio > max_area:
            continue
        if aspect_ratio < calibration.min_box_aspect_ratio:
            continue
        if aspect_ratio > calibration.max_box_aspect_ratio:
            continue

        keep.append(index)

    result.boxes = result.boxes[keep] if keep else result.boxes[:0]
    return result


def box_iou(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_width = max(inter_x2 - inter_x1, 0)
    inter_height = max(inter_y2 - inter_y1, 0)
    intersection = inter_width * inter_height
    area_a = max(ax2 - ax1, 0) * max(ay2 - ay1, 0)
    area_b = max(bx2 - bx1, 0) * max(by2 - by1, 0)
    union = area_a + area_b - intersection
    return intersection / union if union else 0


def box_center_inside(inner_box, outer_box):
    x1, y1, x2, y2 = inner_box
    ox1, oy1, ox2, oy2 = outer_box
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    return ox1 <= cx <= ox2 and oy1 <= cy <= oy2


def run_person_detection(frame, person_model):
    if person_model is None:
        return []
    person_results = person_model(
        frame,
        verbose=False,
        conf=PERSON_CONFIDENCE_THRESHOLD,
        classes=[PERSON_CLASS_ID],
        imgsz=PERSON_IMGSZ,
    )
    return [box.xyxy[0].tolist() for box in person_results[0].boxes]


def apply_person_suppression(result, person_boxes):
    if not person_boxes or not len(result.boxes):
        return result, 0

    keep = []
    suppressed = 0
    for index, box in enumerate(result.boxes):
        candidate = box.xyxy[0].tolist()
        overlaps_person = any(
            box_iou(candidate, person_box) > PERSON_SUPPRESSION_IOU
            or box_center_inside(candidate, person_box)
            for person_box in person_boxes
        )
        if overlaps_person:
            suppressed += 1
            continue
        keep.append(index)

    result.boxes = result.boxes[keep] if keep else result.boxes[:0]
    return result, suppressed


def suppress_person_overlaps(frame, result, person_model, allow_run=True):
    if person_model is None or not len(result.boxes) or not allow_run:
        return result, 0
    person_boxes = run_person_detection(frame, person_model)
    return apply_person_suppression(result, person_boxes)


def detect_fish(
    frame,
    model,
    calibration,
    person_model=None,
    person_boxes=None,
    refresh_person=False,
):
    results = model(
        frame,
        verbose=False,
        conf=inference_confidence(calibration),
        classes=DETECTION_CLASS_IDS,
        imgsz=DETECT_IMGSZ,
    )
    result = filter_result(results[0], frame.shape, calibration)

    if person_model is not None and refresh_person:
        person_boxes = run_person_detection(frame, person_model)
    elif person_boxes is None:
        person_boxes = []

    result, suppressed = apply_person_suppression(result, person_boxes)
    result.tilapiers_suppressed_people = suppressed
    result.tilapiers_person_boxes = person_boxes
    return result


def result_metrics(result):
    confidences = [float(box.conf[0]) for box in result.boxes]
    class_counts = {}

    for box in result.boxes:
        class_id = int(box.cls[0])
        class_name = result.names.get(class_id, str(class_id))
        class_counts[class_name] = class_counts.get(class_name, 0) + 1

    return {
        "count": len(result.boxes),
        "max_confidence": max(confidences) if confidences else 0.0,
        "avg_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
        "class_counts": class_counts,
        "suppressed_people": getattr(result, "tilapiers_suppressed_people", 0),
    }


def hex_to_bgr(hex_color):
    value = str(hex_color).strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return (0, 200, 255)
    try:
        red = int(value[0:2], 16)
        green = int(value[2:4], 16)
        blue = int(value[4:6], 16)
    except ValueError:
        return (0, 200, 255)
    return (blue, green, red)


BOX_COLORS = {
    name: hex_to_bgr(color) for name, color in CLASS_COLORS.items()
}


def box_color(class_name):
    return BOX_COLORS.get(class_name, hex_to_bgr(DEFAULT_BOX_COLOR))


def label_text_color(bgr):
    blue, green, red = bgr
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    return (0, 0, 0) if luminance > 140 else (255, 255, 255)


def annotate_frame(frame, result, calibration):
    annotated = frame.copy()
    font = cv2.FONT_HERSHEY_SIMPLEX

    for box in result.boxes:
        class_id = int(box.cls[0])
        class_name = result.names.get(class_id, str(class_id))
        confidence = float(box.conf[0])
        color = box_color(class_name)

        x1, y1, x2, y2 = (int(round(v)) for v in box.xyxy[0].tolist())
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        label = f"{class_name} {confidence:.2f}"
        (text_w, text_h), baseline = cv2.getTextSize(label, font, 0.55, 2)
        label_top = max(y1 - text_h - baseline - 8, 0)
        cv2.rectangle(
            annotated,
            (x1, label_top),
            (min(x1 + text_w + 10, annotated.shape[1] - 1), y1),
            color,
            -1,
        )
        cv2.putText(
            annotated,
            label,
            (x1 + 5, max(y1 - baseline - 5, text_h + 3)),
            font,
            0.55,
            label_text_color(color),
            2,
            cv2.LINE_AA,
        )

    metrics = result_metrics(result)
    parts = [f"Detections: {metrics['count']}"]
    for name in sorted(metrics.get("class_counts", {})):
        parts.append(f"{name} {metrics['class_counts'][name]}")
    parts.append(f"base conf >= {calibration.confidence:.2f}")
    cv2.putText(
        annotated,
        " | ".join(parts),
        (10, 30),
        font,
        0.7,
        (0, 200, 255),
        2,
        cv2.LINE_AA,
    )
    return annotated, metrics
