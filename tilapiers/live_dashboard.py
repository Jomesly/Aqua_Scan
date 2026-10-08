import threading
import time

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from detection_core import (
    Calibration,
    annotate_frame,
    detect_fish,
    enumerate_camera_names,
    list_cameras,
    load_model,
    load_person_model,
    open_camera,
    parse_camera_source,
    result_metrics,
)
from model_config import CAMERA_INDICES, MODEL_PATH

app = FastAPI(title="Tilapiers Live Dashboard")

model = load_model()
person_model = load_person_model()
calibration = Calibration()
state_lock = threading.Lock()
camera_source = "auto"
camera_enabled = True
last_source_before_off = "auto"
latest_metrics = {
    "count": 0,
    "max_confidence": 0.0,
    "avg_confidence": 0.0,
    "class_counts": {},
    "suppressed_people": 0,
    "stream_fps": 0.0,
    "detect_fps": 0.0,
    "status": "waiting for stream",
    "camera": "auto",
    "camera_label": "Auto",
    "camera_enabled": True,
    "updated_at": None,
}
ZERO_METRICS = {
    "count": 0,
    "max_confidence": 0.0,
    "avg_confidence": 0.0,
    "class_counts": {},
    "suppressed_people": 0,
    "stream_fps": 0.0,
    "detect_fps": 0.0,
}


class CalibrationUpdate(BaseModel):
    confidence: float | None = None
    min_box_area_ratio: float | None = None
    max_box_area_ratio: float | None = None
    preset: str | None = None


class CameraUpdate(BaseModel):
    source: str = "auto"


class CameraPowerUpdate(BaseModel):
    enabled: bool = True


def update_metrics(metrics, status="streaming"):
    label = camera_label(camera_source, camera_enabled)
    with state_lock:
        latest_metrics.update(metrics)
        latest_metrics["status"] = status
        latest_metrics["camera"] = camera_source
        latest_metrics["camera_label"] = label
        latest_metrics["camera_enabled"] = camera_enabled
        latest_metrics["updated_at"] = time.strftime("%H:%M:%S")


def camera_label(source, enabled=True):
    if not enabled:
        return "Off"
    if source in (None, "", "auto"):
        return "Auto"
    text = str(source)
    if text.isdigit():
        names = enumerate_camera_names()
        return names.get(int(text), f"Camera {text}")
    return text


def get_camera_state():
    with state_lock:
        return camera_source, camera_enabled


def set_camera_source(source: str) -> str:
    global camera_source, last_source_before_off
    normalized = source.strip() if source else "auto"
    if not normalized:
        normalized = "auto"
    if normalized.lower() in {"auto", "off", "stop"}:
        normalized = "auto" if normalized.lower() == "auto" else normalized.lower()
    elif normalized.isdigit():
        index = int(normalized)
        if index not in CAMERA_INDICES and index > 7:
            raise ValueError(f"Unsupported camera index: {index}")
        normalized = str(index)

    with state_lock:
        camera_source = normalized
        if camera_enabled:
            last_source_before_off = normalized
        latest_metrics["camera"] = normalized
        latest_metrics["updated_at"] = time.strftime("%H:%M:%S")

    label = camera_label(normalized, camera_enabled)
    with state_lock:
        latest_metrics["camera_label"] = label
        latest_metrics["status"] = (
            f"switching to {label}" if camera_enabled else "camera off"
        )
    return normalized


def set_camera_enabled(enabled: bool) -> bool:
    global camera_enabled, camera_source, last_source_before_off
    with state_lock:
        camera_enabled = bool(enabled)
        if camera_enabled:
            camera_source = last_source_before_off or "auto"
        else:
            if camera_source not in {"off", "stop"}:
                last_source_before_off = camera_source

    if camera_enabled:
        label = camera_label(camera_source, True)
        status = f"switching to {label}"
    else:
        label = "Off"
        status = "camera off"

    with state_lock:
        latest_metrics.update(dict(ZERO_METRICS))
        latest_metrics["camera"] = camera_source
        latest_metrics["camera_label"] = label
        latest_metrics["camera_enabled"] = camera_enabled
        latest_metrics["status"] = status
        latest_metrics["updated_at"] = time.strftime("%H:%M:%S")
        return camera_enabled


def jpeg_frame(frame):
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
    if not ok:
        return None
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
    )


def black_placeholder_jpeg(message="Camera off"):
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.rectangle(frame, (40, 40), (1240, 680), (25, 35, 55), -1)
    cv2.rectangle(frame, (40, 40), (1240, 680), (55, 75, 110), 3)
    cv2.putText(
        frame,
        message,
        (360, 340),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.4,
        (148, 163, 184),
        3,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        "No camera feed is being captured",
        (390, 400),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (100, 116, 139),
        2,
        cv2.LINE_AA,
    )
    return jpeg_frame(frame)


_latest_payload = None
_latest_payload_lock = threading.Lock()
_capture_state = {"running": False, "threads": []}
_shared = {"frame": None, "seq": 0}
_shared_lock = threading.Lock()
_detection_cache = {"result": None, "calibration": None, "updated_at": 0.0}
_detection_lock = threading.Lock()
DETECTION_MAX_AGE = 2.0


def _publish_payload(payload):
    global _latest_payload
    if not payload:
        return
    with _latest_payload_lock:
        _latest_payload = payload


def _get_payload():
    with _latest_payload_lock:
        return _latest_payload


def _set_shared_frame(frame):
    with _shared_lock:
        _shared["frame"] = frame
        _shared["seq"] += 1


def _clear_shared_frame():
    with _shared_lock:
        _shared["frame"] = None
        _shared["seq"] += 1


def _get_shared_frame(last_seq):
    with _shared_lock:
        frame = _shared["frame"]
        seq = _shared["seq"]
    if frame is None or seq == last_seq:
        return None, seq
    return frame, seq


class RateCounter:
    """Tracks how many times it was ticked per second."""

    def __init__(self):
        self._count = 0
        self._window = time.monotonic()
        self.fps = 0.0

    def tick(self):
        self._count += 1
        now = time.monotonic()
        elapsed = now - self._window
        if elapsed >= 1.0:
            self.fps = self._count / elapsed
            self._count = 0
            self._window = now
        return self.fps


def update_detection_metrics(metrics, fps=0.0):
    with state_lock:
        for key, value in metrics.items():
            latest_metrics[key] = value
        latest_metrics["detect_fps"] = round(fps, 2)
        latest_metrics["updated_at"] = time.strftime("%H:%M:%S")


def capture_worker():
    cap = None
    active_source = None
    active_enabled = None
    stream_rate = RateCounter()

    try:
        while True:
            desired_source, power_on = get_camera_state()

            if not power_on:
                if cap is not None:
                    cap.release()
                    cap = None
                active_source = None
                active_enabled = False
                _clear_shared_frame()
                with _detection_lock:
                    _detection_cache["result"] = None
                update_metrics(dict(ZERO_METRICS), "camera off")
                _publish_payload(black_placeholder_jpeg("Camera off"))
                time.sleep(0.12)
                continue

            if active_enabled is False or desired_source != active_source or cap is None:
                if cap is not None:
                    cap.release()
                    cap = None

                cap = open_camera(parse_camera_source(desired_source))
                active_source = desired_source
                active_enabled = True
                _clear_shared_frame()
                with _detection_lock:
                    _detection_cache["result"] = None

                if cap is None:
                    update_metrics(
                        dict(ZERO_METRICS),
                        f"camera unavailable: {camera_label(desired_source, True)}",
                    )
                    _publish_payload(
                        black_placeholder_jpeg(
                            f"Unavailable: {camera_label(desired_source, True)}"
                        )
                    )
                    active_source = None
                    time.sleep(1.0)
                    continue

                update_metrics({}, f"streaming {camera_label(desired_source, True)}")

            ret, frame = cap.read()
            if not ret:
                update_metrics(dict(ZERO_METRICS), "frame read failed - retrying")
                _clear_shared_frame()
                if cap is not None:
                    cap.release()
                    cap = None
                active_source = None
                time.sleep(1.0)
                continue

            _set_shared_frame(frame.copy())

            with _detection_lock:
                cached_result = _detection_cache["result"]
                cached_calibration = _detection_cache["calibration"]
                cached_age = time.monotonic() - _detection_cache["updated_at"]

            if cached_result is not None and cached_age <= DETECTION_MAX_AGE:
                annotated, _ = annotate_frame(frame, cached_result, cached_calibration)
            else:
                annotated = frame

            _publish_payload(jpeg_frame(annotated))

            fps = stream_rate.tick()
            with state_lock:
                latest_metrics["stream_fps"] = round(fps, 2)
    finally:
        if cap is not None:
            cap.release()


def inference_worker():
    person_boxes = []
    person_due_at = 0.0
    last_seq = -1
    infer_rate = RateCounter()

    try:
        while True:
            frame, seq = _get_shared_frame(last_seq)
            if frame is None:
                time.sleep(0.02)
                continue
            last_seq = seq

            now = time.monotonic()
            refresh_person = now >= person_due_at

            with state_lock:
                active_calibration = Calibration(**calibration.as_dict())

            try:
                result = detect_fish(
                    frame,
                    model,
                    active_calibration,
                    person_model,
                    person_boxes=person_boxes,
                    refresh_person=refresh_person,
                )
            except Exception as exc:
                with _detection_lock:
                    _detection_cache["result"] = None
                print(f"inference failed, retrying: {exc}")
                time.sleep(0.2)
                continue

            if refresh_person:
                person_boxes = getattr(result, "tilapiers_person_boxes", person_boxes) or []
                person_due_at = now + 0.5

            with _detection_lock:
                _detection_cache["result"] = result
                _detection_cache["calibration"] = active_calibration
                _detection_cache["updated_at"] = time.monotonic()

            update_detection_metrics(result_metrics(result), infer_rate.tick())
    finally:
        pass


def start_capture_worker():
    if _capture_state["running"]:
        return
    for target, name in (
        (capture_worker, "tilapiers-capture"),
        (inference_worker, "tilapiers-inference"),
    ):
        thread = threading.Thread(target=target, daemon=True, name=name)
        _capture_state["threads"].append(thread)
        thread.start()
    _capture_state["running"] = True


def frame_stream():
    start_capture_worker()
    last_payload = None
    while True:
        payload = _get_payload()
        if payload is not None and payload is not last_payload:
            last_payload = payload
            yield payload
        else:
            time.sleep(0.01)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Tilapiers Live Dashboard</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, Segoe UI, Arial, sans-serif; background: #020617; color: #e2e8f0; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; background: radial-gradient(circle at top left, rgba(14,165,233,.22), transparent 32%), linear-gradient(135deg, #020617, #0f172a 58%, #062134); }
    main { width: min(1500px, calc(100vw - 40px)); margin: 0 auto; padding: 28px 0; }
    header { display: flex; justify-content: space-between; align-items: end; gap: 20px; margin-bottom: 22px; }
    h1 { margin: 0; color: white; font-size: clamp(32px, 5vw, 58px); letter-spacing: -0.04em; }
    .subtitle { margin-top: 8px; color: #94a3b8; }
    .grid { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 18px; align-items: start; }
    .panel { border: 1px solid rgba(255,255,255,.1); background: rgba(15,23,42,.78); border-radius: 24px; padding: 16px; box-shadow: 0 24px 80px rgba(2,6,23,.45); }
    .stream { width: 100%; aspect-ratio: 16 / 9; object-fit: cover; border-radius: 18px; background: #020617; display: block; }
    .cards { display: grid; gap: 12px; }
    .card { border: 1px solid rgba(255,255,255,.1); background: rgba(255,255,255,.04); border-radius: 18px; padding: 14px; }
    .label { color: #94a3b8; font-size: 13px; }
    .value { margin-top: 4px; color: white; font-size: 32px; font-weight: 800; }
    .ok { color: #67e8f9; }
    .warn { color: #fbbf24; }
    .control { margin-top: 14px; }
    .control-row { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; color: #cbd5e1; }
    input[type=range] { width: 100%; accent-color: #06b6d4; margin-top: 8px; }
    select, input[type=text] { width: 100%; margin-top: 8px; border: 1px solid rgba(255,255,255,.14); background: rgba(2,6,23,.7); color: #e2e8f0; border-radius: 12px; padding: 10px 12px; font: inherit; }
    button { width: 100%; margin-top: 14px; border: 0; border-radius: 14px; background: #0891b2; color: white; padding: 12px 14px; font-weight: 800; cursor: pointer; }
    button.secondary { background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.14); }
    button.danger { background: #b91c1c; }
    button.danger:hover { background: #dc2626; }
    .stream-wrap { position: relative; }
    .stream-off {
      position: absolute;
      inset: 0;
      display: none;
      place-items: center;
      border-radius: 18px;
      background: #000;
      color: #94a3b8;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      pointer-events: none;
    }
    .stream-off.visible { display: grid; }
    .start-picker { display: none; margin-top: 12px; padding: 12px; border: 1px solid rgba(34,211,238,.35); background: rgba(8,145,178,.12); border-radius: 14px; }
    .start-picker.visible { display: block; }
    .start-picker .hint { color: #a5f3fc; }
    .settings { border-top: 1px dashed rgba(255,255,255,.14); margin-top: 6px; padding-top: 12px; }
    .hint { margin-top: 8px; color: #94a3b8; font-size: 12px; line-height: 1.4; }
    .insight { color: #cbd5e1; line-height: 1.45; font-size: 14px; }
    @media (max-width: 980px) { .grid { grid-template-columns: 1fr; } header { align-items: start; flex-direction: column; } }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Tilapiers Live</h1>
        <div class="subtitle">Feed-pellet detection with live calibration controls</div>
      </div>
      <div class="panel insight">Model: <span id="modelName" class="ok">loading</span><br/>Classes: <span id="modelClasses">loading</span><br/>Press Ctrl+C in the terminal to stop the server.</div>
    </header>
    <section class="grid">
      <div class="panel">
        <div class="stream-wrap">
          <img class="stream" src="/stream" alt="Tilapiers live fish detection stream" decoding="async" />
          <div id="streamOff" class="stream-off">Camera off - no feed</div>
        </div>
      </div>
      <aside class="cards">
        <div class="card">
          <div class="label">Detections</div>
          <div id="count" class="value">0</div>
        </div>
        <div class="card">
          <div class="label">Detection breakdown</div>
          <div id="breakdown" class="insight" style="margin-top: 8px;">No detections yet</div>
        </div>
        <div class="card">
          <div class="label">Person/background suppression</div>
          <div id="suppressed" class="value warn" style="font-size: 22px;">0 filtered</div>
        </div>
        <div class="card">
          <div class="label">Max confidence</div>
          <div id="confidence" class="value ok">0%</div>
        </div>
        <div class="card">
          <div class="label">Frame rate</div>
          <div id="fps" class="value ok">0.0 fps</div>
          <div class="hint">Detection: <span id="detectFps" class="ok">0.0 fps</span></div>
        </div>
        <div class="card">
          <div class="label">Stream status</div>
          <div id="status" class="value warn" style="font-size: 22px;">starting</div>
          <div class="hint">Active camera: <span id="cameraLabel" class="ok">Auto</span></div>
        </div>
        <div class="card">
          <div class="label">Settings - camera source</div>
          <button id="toggleCamera" class="danger" type="button" data-enabled="true">Stop camera</button>
          <div class="hint">Stop fully releases the webcam. Start scans for cameras and only shows a picker if more than one is found.</div>
          <div id="startPicker" class="start-picker" hidden>
            <div class="label" style="color:#67e8f9;">Multiple cameras detected</div>
            <div class="hint" id="startPickerHint">Choose a camera, then start the feed.</div>
            <div class="control">
              <div class="control-row"><span>Detected source</span><strong id="startPickerLabel">-</strong></div>
              <select id="startPickerSelect" aria-label="Detected camera source"></select>
            </div>
            <button id="startPickerConfirm" type="button">Start selected camera</button>
            <button id="startPickerCancel" class="secondary" type="button">Cancel</button>
          </div>
          <div class="control">
            <div class="control-row"><span>Choose camera</span><strong id="cameraSourceLabel">auto</strong></div>
            <select id="cameraSource" aria-label="Camera source">
              <option value="auto">Auto (first available)</option>
            </select>
            <div id="cameraListHint" class="hint">Only plugged-in cameras are listed (OBS-style). Plug a camera in, then Scan.</div>
          </div>
          <div class="control">
            <div class="control-row"><span>Custom source (index or URL)</span></div>
            <input id="cameraCustom" type="text" placeholder="e.g. 1 or rtsp://user:pass@host/stream" />
          </div>
          <button id="scanCameras" class="secondary" type="button">Scan available cameras</button>
          <button id="applyCamera" type="button">Apply camera</button>
          <div id="cameraMessage" class="hint">Applies without restarting the stream.</div>
        </div>
        <div class="card">
          <div class="label">Calibration</div>
          <div class="control-row"><span>Presets</span><strong id="presetLabel">balanced</strong></div>
          <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 10px;">
            <button type="button" data-preset="sensitive">Sensitive</button>
            <button type="button" data-preset="balanced">Balanced</button>
            <button type="button" data-preset="strict">Strict</button>
          </div>
          <div class="control">
            <div class="control-row"><span>Confidence threshold</span><strong id="confLabel">0.45</strong></div>
            <input id="conf" type="range" min="0.15" max="0.95" step="0.01" value="0.45" />
          </div>
          <div class="control">
            <div class="control-row"><span>Min box area</span><strong id="minAreaLabel">0.05%</strong></div>
            <input id="minArea" type="range" min="0.000" max="0.020" step="0.0005" value="0.0005" />
          </div>
          <div class="control">
            <div class="control-row"><span>Max box area</span><strong id="maxAreaLabel">65%</strong></div>
            <input id="maxArea" type="range" min="0.05" max="0.90" step="0.01" value="0.65" />
          </div>
          <button id="apply">Apply calibration</button>
        </div>
        <div class="card insight">
          Start with Balanced. All 4 classes from Yolo_v8_OBB/best (1).pt are live as rotated boxes: Bubbles (blue), Pellets (red), Tilapia (mint), Waste (white). Keep people out of frame to reduce false positives from skin/clothes.
        </div>
      </aside>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    function pct(value) { return `${Math.round(value * 100)}%`; }
    function syncLabels() {
      $("confLabel").textContent = Number($("conf").value).toFixed(2);
      $("minAreaLabel").textContent = pct(Number($("minArea").value));
      $("maxAreaLabel").textContent = pct(Number($("maxArea").value));
    }
    ["conf", "minArea", "maxArea"].forEach((id) => $(id).addEventListener("input", syncLabels));
    $("apply").addEventListener("click", async () => {
      await fetch("/api/calibration", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          confidence: Number($("conf").value),
          min_box_area_ratio: Number($("minArea").value),
          max_box_area_ratio: Number($("maxArea").value)
        })
      });
    });
    document.querySelectorAll("[data-preset]").forEach((button) => {
      button.addEventListener("click", async () => {
        const preset = button.dataset.preset;
        const res = await fetch("/api/calibration", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ preset })
        });
        const data = await res.json();
        $("presetLabel").textContent = preset;
        $("conf").value = data.confidence;
        $("minArea").value = data.min_box_area_ratio;
        $("maxArea").value = data.max_box_area_ratio;
        syncLabels();
      });
    });
    async function refresh() {
      const res = await fetch("/api/status");
      const data = await res.json();
      $("count").textContent = data.count;
      $("confidence").textContent = pct(data.max_confidence || 0);
      $("status").textContent = data.status;
      $("suppressed").textContent = `${data.suppressed_people || 0} filtered`;
      $("fps").textContent = `${Number(data.stream_fps || 0).toFixed(1)} fps`;
      $("detectFps").textContent = `${Number(data.detect_fps || 0).toFixed(1)} fps`;
      $("modelName").textContent = data.model.name;
      $("modelClasses").textContent = data.model.classes.join(", ");
      const enabled = data.camera_enabled !== false;
      $("cameraLabel").textContent = data.camera_label || (enabled ? "Auto" : "Off");
      $("toggleCamera").dataset.enabled = String(enabled);
      $("toggleCamera").textContent = enabled ? "Stop camera" : "Start camera";
      $("toggleCamera").classList.toggle("danger", enabled);
      $("toggleCamera").classList.toggle("secondary", !enabled);
      $("streamOff").classList.toggle("visible", !enabled);
      if (enabled) hideStartPicker();
      const cameraValue = data.camera ?? "auto";
      if (![...$("cameraSource").options].some((option) => option.value === cameraValue)) {
        const option = document.createElement("option");
        option.value = cameraValue;
        option.textContent = data.camera_label || cameraValue;
        $("cameraSource").appendChild(option);
      }
      if (document.activeElement !== $("cameraSource")) {
        $("cameraSource").value = cameraValue;
        $("cameraSourceLabel").textContent = data.camera_label || cameraValue;
      }
      const entries = Object.entries(data.class_counts || {});
      $("breakdown").textContent = entries.length
        ? entries.map(([name, count]) => `${name}: ${count}`).join(" | ")
        : "No detections yet";
    }

    function hideStartPicker() {
      $("startPicker").classList.remove("visible");
      $("startPicker").hidden = true;
    }

    async function setCameraPower(enabled) {
      const res = await fetch("/api/camera/power", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled })
      });
      if (!res.ok) throw new Error("Failed to toggle camera power");
      return res.json();
    }

    async function setCameraSource(source) {
      const res = await fetch("/api/camera", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source })
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || "Failed to set camera");
      return data;
    }

    async function startCameraWithSource(source) {
      await setCameraSource(source);
      const data = await setCameraPower(true);
      hideStartPicker();
      $("cameraMessage").textContent = `Camera started on ${data.camera_label}`;
      $("cameraSourceLabel").textContent = data.camera_label;
      await refresh();
      return data;
    }

    function fillSelect(select, cameras, includeAuto = true) {
      const current = select.value;
      select.innerHTML = includeAuto ? '<option value="auto">Auto (first available)</option>' : "";
      cameras.forEach((camera) => {
        const option = document.createElement("option");
        option.value = camera.source;
        option.textContent = camera.label;
        select.appendChild(option);
      });
      if ([...select.options].some((option) => option.value === current)) {
        select.value = current;
      }
      return select;
    }

    async function scanCameras({ applyToMain = true } = {}) {
      $("cameraMessage").textContent = "Scanning cameras...";
      try {
        const res = await fetch("/api/cameras");
        const data = await res.json();
        const detected = data.detected || [];
        if (applyToMain) {
          fillSelect($("cameraSource"), detected, true);
        }
        $("cameraListHint").textContent = detected.length
          ? `${detected.length} connected: ${detected.map((camera) => camera.label).join(", ")}`
          : "No cameras found - plug one in and Scan";
        $("cameraMessage").textContent = detected.length
          ? `Found ${detected.length} camera${detected.length === 1 ? "" : "s"}`
          : "No cameras found";
        return detected;
      } catch (error) {
        $("cameraMessage").textContent = "Camera scan failed";
        return [];
      }
    }

    async function toggleCamera() {
      const currentlyEnabled = $("toggleCamera").dataset.enabled !== "false";
      if (currentlyEnabled) {
        $("toggleCamera").textContent = "Stopping...";
        try {
          await setCameraPower(false);
          hideStartPicker();
          $("cameraMessage").textContent = "Camera stopped - feed blacked out";
          await scanCameras();
          await refresh();
        } catch (error) {
          $("cameraMessage").textContent = "Failed to toggle camera";
          await refresh();
        }
        return;
      }

      $("toggleCamera").textContent = "Scanning...";
      try {
        const detected = await scanCameras();

        if (detected.length === 0) {
          await startCameraWithSource("auto");
          $("cameraMessage").textContent = "No camera found - started with Auto";
          return;
        }

        if (detected.length === 1) {
          await startCameraWithSource(detected[0].source);
          $("cameraMessage").textContent = `Started ${detected[0].label}`;
          return;
        }

        const select = $("startPickerSelect");
        fillSelect(select, detected, false);
        select.value = detected[0].source;
        $("startPickerLabel").textContent = detected[0].label;
        $("startPickerHint").textContent = `${detected.length} cameras connected. Choose one to start the feed.`;
        $("startPicker").hidden = false;
        $("startPicker").classList.add("visible");
        $("cameraMessage").textContent = `${detected.length} cameras connected - choose one below`;
        $("toggleCamera").textContent = "Start camera";
      } catch (error) {
        $("cameraMessage").textContent = "Camera scan failed";
        $("toggleCamera").textContent = "Start camera";
        await refresh();
      }
    }

    function cameraPayloadFromUi() {
      const custom = $("cameraCustom").value.trim();
      if (custom) return custom;
      return $("cameraSource").value;
    }

    async function applyCamera() {
      const source = cameraPayloadFromUi();
      $("cameraMessage").textContent = "Switching camera...";
      try {
        const data = await setCameraSource(source);
        if (data.ok === false) throw new Error(data.error || "Failed to switch camera");
        $("cameraMessage").textContent = `Using ${data.camera_label}`;
        $("cameraSourceLabel").textContent = data.camera_label;
        await refresh();
      } catch (error) {
        $("cameraMessage").textContent = error.message || "Failed to switch camera";
      }
    }

    $("applyCamera").addEventListener("click", applyCamera);
    $("toggleCamera").addEventListener("click", toggleCamera);
    $("cameraSource").addEventListener("change", applyCamera);
    $("startPickerSelect").addEventListener("change", () => {
      const option = $("startPickerSelect").selectedOptions[0];
      $("startPickerLabel").textContent = option ? option.textContent : "-";
    });
    $("startPickerConfirm").addEventListener("click", async () => {
      const source = $("startPickerSelect").value;
      $("startPickerConfirm").textContent = "Starting...";
      try {
        await startCameraWithSource(source);
        $("cameraMessage").textContent = `Camera started on ${$("cameraSourceLabel").textContent}`;
      } catch (error) {
        $("cameraMessage").textContent = error.message || "Failed to start camera";
      } finally {
        $("startPickerConfirm").textContent = "Start selected camera";
      }
    });
    $("startPickerCancel").addEventListener("click", () => {
      hideStartPicker();
      $("toggleCamera").textContent = "Start camera";
      $("cameraMessage").textContent = "Start cancelled - camera remains off";
    });
    $("scanCameras").addEventListener("click", () => scanCameras());

    syncLabels();
    setInterval(refresh, 750);
    refresh();
    scanCameras();
    setInterval(scanCameras, 4000);
  </script>
</body>
</html>
"""


@app.get("/stream")
def stream():
    return StreamingResponse(frame_stream(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/status")
def status():
    with state_lock:
        return {
            **latest_metrics,
            "calibration": calibration.as_dict(),
            "camera": camera_source,
            "camera_label": camera_label(camera_source, camera_enabled),
            "camera_enabled": camera_enabled,
            "model": {
                "name": MODEL_PATH.name,
                "path": str(MODEL_PATH),
                "classes": list(model.names.values()),
            },
        }


@app.get("/api/cameras")
def cameras():
    try:
        found = list_cameras()
    except Exception as exc:
        return {"cameras": [], "detected": [], "error": str(exc)}

    return {"cameras": found, "detected": found}


@app.post("/api/camera")
def update_camera(update: CameraUpdate):
    try:
        source = set_camera_source(update.source)
    except ValueError as exc:
        with state_lock:
            return {
                "ok": False,
                "error": str(exc),
                "camera": camera_source,
                "camera_label": camera_label(camera_source, camera_enabled),
                "camera_enabled": camera_enabled,
            }

    with state_lock:
        return {
            "ok": True,
            "camera": source,
            "camera_label": camera_label(source, camera_enabled),
            "camera_enabled": camera_enabled,
            "status": latest_metrics["status"],
        }


@app.post("/api/camera/power")
def update_camera_power(update: CameraPowerUpdate):
    enabled = set_camera_enabled(update.enabled)
    with state_lock:
        return {
            "ok": True,
            "camera_enabled": enabled,
            "camera": camera_source,
            "camera_label": camera_label(camera_source, enabled),
            "status": latest_metrics["status"],
        }


@app.post("/api/calibration")
def update_calibration(update: CalibrationUpdate):
    with state_lock:
        if update.preset is not None:
            calibration.apply_preset(update.preset)
            return calibration.as_dict()

        if update.confidence is not None:
            calibration.confidence = min(max(update.confidence, 0.05), 0.99)
        if update.min_box_area_ratio is not None:
            calibration.min_box_area_ratio = min(max(update.min_box_area_ratio, 0.0), 0.2)
        if update.max_box_area_ratio is not None:
            calibration.max_box_area_ratio = min(max(update.max_box_area_ratio, 0.05), 0.9)
        if calibration.min_box_area_ratio > calibration.max_box_area_ratio:
            calibration.min_box_area_ratio = calibration.max_box_area_ratio

        return calibration.as_dict()
