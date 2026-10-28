# Tilapiers

**A smart hybrid YOLO26 and regression-based framework for environment monitoring, fish health monitoring, and harvest readiness assessment in outdoor Nile tilapia ponds.**

Thesis prototype, CS 307, Technological Institute of the Philippines – Quezon City.

Tilapiers is a monitoring and decision-support tool. It screens visible indicators, refers flagged fish to a technician, and records a rule-based readiness status per pond. It does **not** diagnose disease, forecast harvest dates, or make the harvest decision.

## Modules

| Module | What it does | Status in this prototype |
|---|---|---|
| **Environment Monitoring** | Logs water temperature from the existing DS18B20 probe, adds the Philippine season and the caretaker's daily yes/no algae report (plus optional DO / pH / ammonia / nitrate), and classifies each pond as Good, Moderate or Critical. Computes stress exposure between sampling rounds. | Working with real hardware (USB) or network upload. Safe band fixed at **24–31 °C**. |
| **Fish Health Monitoring** | Caretaker photographs each sampled fish on the board. An image-quality check runs, a detector finds the fish and its regions, indicators are measured, and a regression gives the Fish Condition Index (FCI). Pond status is Normal, Watch or Refer to technician. | Pipeline is complete end to end. The quality check is real. The detector is a **labeled placeholder** until YOLO26 is trained. FCI regression fitting and grouped cross-validation are real. |
| **Harvest Readiness** | Share of fish at target size, weight uniformity (CV), specific growth rate, a degree-2 growth curve once 5 or more rounds exist, condition factor, days of culture, and health clearance give Not Ready, Approaching or Ready. | Working. Target size and cutoffs are provisional. |

The **Evaluation** page reports what the panel needs:
- FCI regression, with a comparison across indicator groups and leave-one-pond-out cross-validation
- probe vs reference thermometer error
- agreement with the technician's independent assessments (accuracy, Cohen's κ, confusion matrix)
- the association between environment and fish condition
- image length error
- CSV exports

## Repository layout

```
firmware/tilapiers_probe/   DS18B20 + LCD sketch (unchanged hardware from the previous build)
backend/                    FastAPI + SQLite
  tilapiers/rules/          pure, unit-tested decision rules (environment, health, harvest, evaluation)
  tilapiers/vision/         image-quality check, detector interface, indicator measurement
  tilapiers/sensors/        USB serial probe reader, demo simulator
  tilapiers/services.py     domain logic on top of rules + database
  tilapiers/api.py          HTTP API (/api/...)
  tilapiers/seed.py         demo data for presentations
  tests/                    pytest suite
frontend/                   React + Vite dashboard (mobile-first for caretakers)
docs/ARCHITECTURE.md        how the pieces fit together
```

## Run it

Requirements: Python 3.12, Node 20+.

**Demo for the panel** (seeded ponds and a simulated probe, all clearly labeled):

```powershell
powershell -ExecutionPolicy Bypass -File .\run-demo.ps1
```

Then open http://127.0.0.1:8000. Because it listens on all interfaces, a phone on the same Wi-Fi can open `http://<laptop-ip>:8000` and use the sampling flow with its camera.

**Field use with the real probe:**

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env        # set TILAPIERS_SERIAL_POND, notification channel, etc.
cd ..\frontend; npm install; npx vite build; cd ..\backend
.venv\Scripts\python -m uvicorn tilapiers.main:app --host 0.0.0.0 --port 8000
```

Plug the probe in by USB. It is discovered automatically; Bluetooth serial ports are skipped. If no probe is found, the pond shows **Probe offline**. The system never substitutes fake readings.

**Frontend development** (hot reload; proxies `/api` to the backend on port 8000):

```powershell
cd frontend; npm run dev        # http://localhost:5173
```

**Tests:**

```powershell
cd backend; .venv\Scripts\python -m pytest
```

## Open decisions (study team)

- **Alert channel:** email or SMS. Set `TILAPIERS_NOTIFY_CHANNEL`. Email works over SMTP today. SMS is recorded as *not sent* until a provider is chosen.
- **Environment inputs beyond temperature:** currently season plus the caretaker's algae yes/no and optional water tests. Public weather data can be added later without changing the rules' interface.
- **Thresholds:** every cutoff except the 24–31 °C band is marked *provisional* in Settings, to be set with the BFAR technician (Chapter 3).
- **YOLO26 model:** train on the annotated sampling-board photos (classes `fish`, `eye`, `gill`, `fin`, `scale`), then set `TILAPIERS_YOLO_WEIGHTS`.

## Previous study

The earlier feeding/DO/temperature-only builds are preserved in git as the `legacy/*` branches and in `C:\CodingProjects\Aqua_Scan_legacy_inner.bundle`.
