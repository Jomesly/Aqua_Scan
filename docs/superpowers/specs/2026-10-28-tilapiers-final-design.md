# Tilapiers (final study) — System Design

Date: 2026-10-28 · Source of truth: *BROAD_STUDIES (7).docx* (final paper, CS 307, TIP-QC)

## 1. Intent

Rebuild Tilapiers to match the final paper. It's a web app that turns a caretaker's
sampling round (photos of fish on a marked board, plus scale weight and ruler length)
into three things: a disease-screening Health status, weight and biomass estimates,
and a Harvest readiness status. Flagged fish go to a BFAR technician for review.

**Why now:** the study's focus changed and the paper is final. The current uncommitted
rebuild (DS18B20 temperature probe, environment monitoring, FCI) contradicts the paper's
scope ("No sensors… water temperature… not measured or used in any status").

**Success:**
1. **Panel live demo:** the whole flow runs on one laptop. Real photos uploaded from a
   phone on the same Wi-Fi get screened by the team's trained **YOLOv8s** model, and the
   statuses, charts and evaluation pages are populated.
2. **BFAR prototype:** at least half the system is *genuinely working, not mocked*. Every
   placeholder or provisional value is visibly labeled as one.

## 2. Goals / non-goals / anti-goals

**Goals:** all modules in paper Table 4 and use cases UC1–UC10 (Table 5); the
per-fish pipeline (Figure 4 / Figure 9 / Figure 10); the rules in Figure 11; the
evaluation metrics in Chapter 3.

**Non-goals:** water quality, sensors, firmware, notifications by SMS or email, behavior
analysis, treatment advice, harvest-date forecasting beyond the observed days, training
models inside the app, cloud deployment (the paper says cloud DB and storage; the demo
runs locally, see §7).

**Anti-goals (a failure even if it "works"):**
- A fabricated number shown as real: a fake detection, a fake length when there's no scale, a fake weight model.
- A pond shown **Ready** while its Health status isn't Normal.
- Language that reads as a diagnosis ("has TiLV") instead of a screen ("signs consistent with TiLV").
- Any status cutoff hard-coded where the admin can't change it.

## 3. Constraints

- Windows laptop, **CPU only** (no GPU). Python 3.12 (existing `backend/.venv`), Node 20+.
- Model: `yolov8s_best.pt`, Ultralytics **detect** model, classes `Healthy, Aeromonas, TiLV`,
  640 px. Benchmarks (paper Table 10): P 0.897, R 0.675, mAP50 0.683, Aeromonas AP50 0.302.
  It has **no segmentation head**.
- The sampling board isn't built yet. Its size isn't fixed (paper: "to be fixed when the board is made").
- All cutoffs in paper Table 14 are still "[to be set with the BFAR technician]".

## 4. Decisions already made (with the user)

| Decision | Choice |
|---|---|
| Scope | Replace the sensor/environment rebuild with the paper's design |
| Screening model | Team's YOLOv8s now; loader is model-agnostic so YOLO26s weights drop in via config |
| Purpose | Live panel demo first; must be ≥50 % genuinely working for a BFAR prototype |
| Demo photos | Both: real fish on a board, and public-dataset photos |
| Stack | Keep FastAPI + SQLite backend and React + Vite frontend (reuse what fits) |

## 5. Builder's calls (made by Claude, open to change)

1. **Board markers = ArUco** (OpenCV `DICT_4X4_50`, IDs 0–3 = TL, TR, BR, BL). The app
   serves a printable board (A3 by default, inner size configurable in Maintenance). The
   size is entered once the physical board exists.
2. **Interim fish outline = classical segmentation** on the flat-view board (the matte
   board vs. the fish: Otsu/GrabCut seeded by the YOLO box). This gives real length (the
   longest line across the outline) and area in cm. It's labeled "outline: interim
   (classical)" until a YOLO segmentation model is configured. If a `*-seg.pt` is set
   in config, that one is used instead.
3. **No markers, so no scale.** Paper Step 2 says a missing marker fails the check. In
   **board mode** (the default), it does. A per-round toggle **"Public/test photos (no board)"**
   skips the marker requirement. Those fish get screened, but length, area, weight and K are
   "not measured", and the fish's health uses the screen only (K counts as unknown, never as in range).
4. **The weight model before any fit** is a provisional length–weight curve W = a·Lᵇ
   (tilapia literature defaults a = 0.0141, b = 3.0, editable). It's labeled "provisional,
   not fitted". Once at least 10 fish with scale weight and image L/A exist, the admin
   presses **Fit** to run linear (L, A) and degree-2 (L, A, L², A², L·A) regression with
   backward elimination, compared by grouped CV (leave one pond out, or leave one round out
   if there's a single pond). The kept model follows the paper's rule: degree-2 only if CV
   RMSE is clearly lower (≥5 %); otherwise linear. Fitted models are versioned, and
   completed rounds keep the model they used.
5. **Provisional default cutoffs** (all editable, each change saved with its date, shown as
   "provisional" until the admin ticks "confirmed with technician"):
   detection conf 0.25; referral conf 0.50; K accepted range 0.9–2.0; pond Watch if ≥10 %
   of fish are Watch/Refer, pond Refer if ≥1 Refer fish **or** ≥30 % Watch/Refer; target
   size 300 g (about 3–4 fish per kg, a common PH market size); share at target: Approaching ≥ 50 %, Ready ≥ 80 %; max CV 25 %; min SGR
   0.5 %/day; usual culture period 120–180 days.
6. **Readiness classification** (paper Step 5 "how many cutoffs it meets"). Five
   indicators: share at target ≥ Ready cutoff, CV ≤ max, SGR ≥ min (or curve slope > 0
   with 5+ rounds), mean K within range, DOC ≥ the period's lower bound. All five met
   means meets readiness, then the health clearance. If share ≥ the Approaching cutoff
   and at least 3 are met, it's Approaching. Otherwise it's Not Ready. When there's
   only one round, growth is "insufficient data" and counts as not met.
7. **Two photos per fish:** length and area are the mean of both sides. Class is the
   **disease class with the higher confidence** if either side shows one (paper Step 10).
   Otherwise it's Healthy with the max confidence. With no detection above threshold, the
   fish is "No fish detected" and the photo goes back for a retake.
8. **Screening input:** the model runs on the flat-view image cropped to the outline's
   bounding box (paper Step 7). In no-board mode it runs on the raw photo.
9. **Auth:** username + password (PBKDF2 hashed), signed session cookie, three roles.
   Seeded accounts: `admin`, `caretaker`, `technician` (demo passwords shown on the
   login page only while demo mode is on).
10. **Storage:** local SQLite + an `uploads/` folder under `backend/data/`. Backup means
    downloading a zip of the DB and uploads; restore means uploading that zip (admin only).
11. **Demo seed:** 2 ponds, 4–6 historical rounds each, with weights following a
    plausible growth curve. One pond is Ready, the other is Approaching with a Watch.
    Seeded fish have no photos and carry `source = "demo"`, shown as a "Demo data" badge.
    Real uploads are never mixed with seeded statistics in the model-fitting data unless
    the admin opts in.

## 6. What gets built

### Backend (FastAPI, `backend/tilapiers/`)
- `rules/`: pure, unit-tested.
  - `health.py`: K, fish status, pond status.
  - `weight.py`: OLS, backward elimination, grouped CV, metrics R², RMSE, MAE, MARE, MXAE, MXRE.
  - `harvest.py`: SGR, CV, degree-2 growth curve, readiness and clearance.
  - `evaluation.py`: accuracy, weighted κ (linear weights), confusion matrix, Refer recall, retake rate.
  - `thresholds.py`: the cutoff set.
- `vision/`
  - `quality.py`: sharpness and glare, kept.
  - `board.py`: ArUco detection, homography, cm/px, framing check (fish inside markers).
  - `outline.py`: classical or YOLO-seg mask, then length and area.
  - `screening.py`: Ultralytics loader and two-sided merge.
  - `pipeline.py`: per-photo then per-fish processing, returning annotated images.
- Services and API for: auth and users, ponds and stocking, cutoffs with history, rounds
  (create → upload per fish → process batch → retake → complete and snapshot), technician
  review and pond assessments, weight-model fit, evaluation and CSV export, backup and
  restore, FAQ and About content (DB rows, editable by admin), printable board.
- Remove: `sensors/`, `monitor.py`, `notify.py`, environment rules, `firmware/`, pyserial.

### Frontend (React + Vite, mobile-first for the caretaker)
Pages by role:
- **Login**
- **Dashboard:** pond cards with Health and Readiness badges
- **Pond:** latest statuses with their indicators, a growth chart with the 5-round curve, round history
- **New round** (UC2)
- **Round capture** (UC3/3a): per fish, Side A and Side B camera/file inputs, scale W and ruler L inputs, an immediate quality result, and retake
- **Round results** (UC4/5): per-fish annotated photo, class and confidence, L, A, W, K, status, plus average weight and biomass
- **Technician review queue** (UC9): flagged fish, the technician's sign check, pond assessments
- **Maintenance** (UC10): ponds, users, cutoffs with history, weight model fit, board size and printable board, backups
- **Evaluation:** paper Tables 10 and 11, the live weight-model comparison (Table 12 format), status agreement (κ_w, confusion matrix), length/weight error vs ruler and scale, retake rate, CSV export
- **FAQs, About Us**
- **Profile** (UC1): change password

Disclaimers on result pages: "Screening, not diagnosis. Harvest decision stays with the caretaker and technician."

## 7. Left to the builder
Layout and visual design (reuse existing components and charts), exact API routes, DB
schema details, test layout, and how the run script launches the demo. Paper vs. build
differences, to note in the README: local SQLite instead of a cloud DB; YOLOv8s instead of
YOLO26s; classical outline instead of YOLO26-seg (until trained).

## 8. Honesty labels (must appear in the UI)
Demo data · Provisional cutoff · Provisional weight model (not fitted) · Outline: interim
(classical) · No scale: not measured · Screening model: YOLOv8s (from config).
