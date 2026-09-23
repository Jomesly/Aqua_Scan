import threading
import time

import cv2
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from detection_core import Calibration, annotate_frame, detect_fish, load_model, load_person_model, open_camera
from model_config import MODEL_PATH

app = FastAPI(title="Tilapiers Live Dashboard")

model = load_model()
person_model = load_person_model()
calibration = Calibration()
state_lock = threading.Lock()
latest_metrics = {
    "count": 0,
    "max_confidence": 0.0,
    "avg_confidence": 0.0,
    "class_counts": {},
    "suppressed_people": 0,
    "status": "waiting for stream",
    "updated_at": None,
}


class CalibrationUpdate(BaseModel):
    confidence: float | None = None
    min_box_area_ratio: float | None = None
    max_box_area_ratio: float | None = None
    preset: str | None = None


def update_metrics(metrics, status="streaming"):
    with state_lock:
        latest_metrics.update(metrics)
        latest_metrics["status"] = status
        latest_metrics["updated_at"] = time.strftime("%H:%M:%S")


def frame_stream():
    cap = open_camera()
    if cap is None:
        update_metrics({"count": 0, "max_confidence": 0.0, "avg_confidence": 0.0}, "camera unavailable")
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                update_metrics({"count": 0, "max_confidence": 0.0, "avg_confidence": 0.0}, "frame read failed")
                break

            with state_lock:
                active_calibration = Calibration(**calibration.as_dict())

            result = detect_fish(frame, model, active_calibration, person_model)
            annotated, metrics = annotate_frame(frame, result, active_calibration)
            update_metrics(metrics)

            ok, buffer = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            if not ok:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            )
    finally:
        cap.release()


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
    button { width: 100%; margin-top: 14px; border: 0; border-radius: 14px; background: #0891b2; color: white; padding: 12px 14px; font-weight: 800; cursor: pointer; }
    .insight { color: #cbd5e1; line-height: 1.45; font-size: 14px; }
    @media (max-width: 980px) { .grid { grid-template-columns: 1fr; } header { align-items: start; flex-direction: column; } }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Tilapiers Live</h1>
        <div class="subtitle">Tilapia, pellets, and waste detection with live calibration controls</div>
      </div>
      <div class="panel insight">Model: <span id="modelName" class="ok">loading</span><br/>Classes: <span id="modelClasses">loading</span><br/>Press Ctrl+C in the terminal to stop the server.</div>
    </header>
    <section class="grid">
      <div class="panel">
        <img class="stream" src="/stream" alt="Tilapiers live fish detection stream" />
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
          <div class="label">Stream status</div>
          <div id="status" class="value warn" style="font-size: 22px;">starting</div>
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
          Start with Balanced. Active model is weights/best.pt (Tilapia, pellets, waste). Keep people out of frame to reduce false positives from skin/clothes.
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
      $("modelName").textContent = data.model.name;
      $("modelClasses").textContent = data.model.classes.join(", ");
      const entries = Object.entries(data.class_counts || {});
      $("breakdown").textContent = entries.length
        ? entries.map(([name, count]) => `${name}: ${count}`).join(" | ")
        : "No detections yet";
    }
    syncLabels();
    setInterval(refresh, 750);
    refresh();
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
            "model": {
                "name": MODEL_PATH.name,
                "path": str(MODEL_PATH),
                "classes": list(model.names.values()),
            },
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
