# Tilapiers

**TILAPIERS: A Smart Hybrid YOLO26 and Regression-Based Framework for Health Monitoring, Weight Estimation, and Harvest Readiness Assessment for Nile Tilapia Outdoor Ponds**

Thesis prototype, CS 307, Technological Institute of the Philippines, Quezon City.

Tilapiers is a web app for the caretaker's sampling round. The caretaker photographs each sampled fish (both sides) on a sampling board with four corner markers, then weighs it and measures it. The system:

1. checks image quality, finds the markers and corrects the photo to a flat view with a known scale;
2. outlines the fish and measures its **length and area**;
3. screens it with the team's YOLO model and flags visible skin defects: **Skin erosion** (eroded skin, missing scales, pale patches), **Red sores** (bleeding sores, ulcers, reddened fins) or **Healthy** (no visible defect). It does not name a disease;
4. estimates its **weight** by regression and computes the condition factor K;
5. gives the fish and the pond a **Health status** (Normal / Watch / Refer to technician) and the pond a **Harvest readiness status** (Not Ready / Approaching / Ready, with health as a clearance check).

It screens; it does **not** diagnose, recommend treatment, or make the harvest decision. No sensors are installed at the ponds.

## What is real and what is interim

| Part | State |
|---|---|
| Login, roles (caretaker, technician, admin), profile, password | Working |
| Ponds and stocking, users, cutoffs with a dated history, backup and restore | Working |
| Sampling round: create, upload both sides per fish, retake, complete | Working |
| Image-quality check (sharpness, exposure, glare) | Working. Thresholds are starting values to tune on pilot photos. |
| Board markers, flat-view correction, cm scale | Working (ArUco `DICT_4X4_50`, printable board in Maintenance) |
| Disease screening | **Working with the team's YOLOv8s** (`backend/models/yolov8s_best.pt`). YOLO26s can be swapped in through `.env`. |
| Fish outline (length, area) | **Interim:** classical segmentation on the flat-view board, labeled "classical", until a YOLO segmentation model is trained (`TILAPIERS_SEG_WEIGHTS`). |
| Weight regression: linear vs degree-2, backward elimination, grouped CV | Working. A **provisional** W = a·Lᵇ curve is used until 10 or more fish with scale weights exist and the admin presses *Fit*. |
| Health and Harvest readiness rules | Working. **Cutoffs are provisional** until the admin marks them confirmed with the BFAR technician. |
| Technician review of flagged fish, pond assessments | Working |
| Evaluation: paper Tables 10 and 11, training curve, weight-model table, κ_w agreement, Refer recall, length and weight error, retake rate, CSV export | Working |
| FAQs, About Us (editable by admin) | Working |

**Differences from the paper (temporary):** local SQLite and file storage instead of a cloud database; YOLOv8s instead of YOLO26s for screening (YOLOv8s ranked first in four of the five weightings in Table 11); classical outline instead of YOLO26-seg.

## Run the demo (for the panel)

Requirements: Windows, Python 3.12, Node 20+. The screening model `backend/models/yolov8s_best.pt` is included in the repo.

```powershell
powershell -ExecutionPolicy Bypass -File .\run-demo.ps1          # add -Reset for a fresh demo database
```

Open http://127.0.0.1:8000. The script also prints the laptop's address, so a phone on the same Wi-Fi can open it and take photos with its camera.

| Account | Password | Sees |
|---|---|---|
| caretaker | caretaker123 | Dashboard, new sampling round, results, history, FAQs |
| technician | technician123 | Dashboard, review queue, evaluation |
| admin | admin123 | Everything, plus Maintenance |

Demo mode seeds two ponds with completed rounds (all marked **Demo data**). Pond 1 is Ready. Pond 2 is Approaching, with two fish referred to the technician.

**Demo tips**
- *Real fish on the board:* print the board (Maintenance → Board → PDF, at 100 % scale) and run a round with "Sampling board" on.
- *Public dataset photos:* when creating the round, choose "Public / test photos (no board)". Fish are screened, but length and weight show "No scale: not measured". Checked skin-erosion, red-sore and no-defect pairs are in `docs/demo-photos/`. In this mode a photo that fails the quality check is still screened, with a note; with the board it must be retaken.

## Field use

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env        # set TILAPIERS_SECRET_KEY and TILAPIERS_ADMIN_PASSWORD
cd ..\frontend; npm install; npx vite build; cd ..\backend
.venv\Scripts\python -m uvicorn tilapiers.main:app --host 0.0.0.0 --port 8000
```

On first start, one administrator account is created: `admin`, with the password from `TILAPIERS_ADMIN_PASSWORD` (default `admin123`). **Change it right away.**

## Development

```powershell
cd backend; .venv\Scripts\python -m pytest          # backend tests
cd frontend; npm run dev                             # http://localhost:5173, proxies /api to :8000
```

See `docs/ARCHITECTURE.md` for how the pieces fit together. The design is in `docs/superpowers/specs/2026-10-28-tilapiers-final-design.md`.
