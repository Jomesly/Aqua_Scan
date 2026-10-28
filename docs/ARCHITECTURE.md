# Architecture

```
 Pond                         Server (laptop / BFAR PC)                          Browser
┌─────────────────┐   USB    ┌───────────────────────────────────────────┐    ┌──────────────────┐
│ DS18B20 probe   │─serial──►│ sensors/serial_probe  ─┐                  │    │ React dashboard  │
│ + ESP32 + LCD   │          │                        ▼                  │    │  Overview        │
│ (firmware/)     │  HTTP    │ /api/ingest ──► monitor.py (every N s)    │    │  Pond: Env /     │
│ future: buffered│─batch───►│                 │ record reading          │◄──►│   Health/Harvest │
│ upload          │          │                 │ evaluate env state      │/api│  Sampling (phone)│
└─────────────────┘          │                 │ notify on transition    │    │  Round detail    │
                             │                 ▼                         │    │  Alerts          │
 Caretaker phone ───photo───►│ vision/quality → vision/detector →        │    │  Evaluation      │
 (sampling board) + W, L     │ vision/indicators → rules/health (FCI)    │    │  Settings        │
                             │                 ▼                         │    └──────────────────┘
                             │ services.py ◄──► db.py (SQLite, WAL)      │
                             │                 ▼                         │
                             │ notify.py: dashboard always; email/SMS    │
                             │            pluggable, honest status       │
                             └───────────────────────────────────────────┘
```

## Layers

- **`rules/`** holds pure functions with no I/O, which makes them easy to test and to defend to the panel. Every cutoff comes from `Thresholds`, which is stored in the database and editable in Settings.
  - `environment.py` gives the Good/Moderate/Critical/Unknown state, the PAGASA season, and stress-exposure features: hours outside the band, min, max, mean daily range, maximum rate of change on hourly means, and coverage. A gap of more than 2 h counts as missing data, never as exposure.
  - `health.py` has Fulton's K, FCI prediction, OLS fitting with degree-2 terms at most, grouped cross-validation (leave one pond out, or leave one round out with a single pond), the indicator-group comparison, and the Normal/Watch/Refer status.
  - `harvest.py` has SGR, round size statistics, a degree-2 growth curve (5 or more rounds, observed range only), and the readiness status. If the size is reached but health isn't clear, the status is "Size reached – health review needed", never Ready.
  - `evaluation.py` has probe calibration error, agreement with Cohen's κ, and the stress association (OLS with pond fixed effects, descriptive only).
- **`vision/`** is the pipeline that runs at the sampling station.
  - `quality.py` measures sharpness (Laplacian variance), exposure and glare from the pixels.
  - `detector.py` is a `Detection` interface. `YoloDetector` loads Ultralytics weights when configured; `StubDetector` returns deterministic placeholder regions. Each result carries an `is_stub` flag, and the UI, evaluation and exports all respect it. Stub detections give no image length and don't count toward length error.
  - `indicators.py` measures the gill redness, skin, eye clarity, fin ratio and body-shape indices, with gray-world lighting correction until the color card is detected.
- **`services.py`** orchestrates the rules and the database. A round stays a live-updating draft until it's completed. Completing it stores a snapshot of the assessment, so the record doesn't change when thresholds or the model change later.
- **`monitor.py`** is a background thread. It logs the probe at the configured interval, re-evaluates every pond, and notifies on state transitions only.
- **`main.py`** is an app factory with a lifespan hook. Importing it touches no hardware or database.

## Data model (SQLite)

`ponds` → `temperature_readings` (with source), `observations` (algae y/n, optional water tests), `sampling_rounds` (capture metadata, draft/completed, snapshot, technician assessments) → `fish` (W, L, indicators, FCI, flag, QC, detection, technician score). Plus `notifications` (per-channel delivery records), `probe_calibrations`, `env_state` (for transition detection) and `settings` (thresholds, FCI model, contact).

## Gaps in the previous build and how they were addressed

| Previous gap | Now |
|---|---|
| SMS alerts were faked as "delivered" with invented timestamps | Notifier records real per-channel outcomes. The dashboard is always delivered, email is sent over SMTP when configured, and SMS is recorded as *not sent* until a provider is chosen. |
| `/stream` proxy pointed at a missing endpoint | Removed; the frontend polls and pauses polling while the tab is hidden. |
| Silent fallback to simulated temperature when the probe disconnected | The simulator only runs when explicitly enabled (demo). A missing or stale probe shows **Probe offline / Unknown**, never Safe. Every reading stores its source, and synthetic data is labeled in the UI and exports. |
| Bridge reported success even when the port failed to open; stale value repeated forever | `SerialProbe.start()` reports failure; readings carry timestamps and expire. |
| Hardware probing and DB setup at import time; no tests | App factory with lifespan; 65 pytest tests, including an end-to-end demo scenario. |
| Nested repos, duplicated scripts, venvs, DB and thesis files in the tree | Single repo with `firmware/`, `backend/` and `frontend/`; runtime data under the git-ignored `backend/data/`. |
| Hard-coded phone number and COM port | Configured through `.env` and the Settings page; the port is auto-discovered. |
