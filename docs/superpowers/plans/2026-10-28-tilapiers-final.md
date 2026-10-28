# Tilapiers (final study) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sensor-based rebuild with the paper's design. A caretaker records a sampling round of fish photographed on an ArUco board. The system screens each fish with the team's YOLOv8s model, measures length and area, estimates weight, and assigns the Health and Harvest readiness statuses. A technician reviews the flagged fish, and an admin maintains ponds, users, cutoffs and backups.

**Architecture:** FastAPI + SQLite backend split into pure `rules/` (tested), `vision/` (board → outline → screening pipeline), `services.py` (orchestration and DB), `api.py` (REST + cookie session auth). A React + Vite SPA is served by the backend; it's mobile-first for caretakers and has role-based navigation.

**Tech Stack:** Python 3.12, FastAPI, SQLite, NumPy, OpenCV (aruco), Ultralytics (CPU torch), itsdangerous; React 18, react-router 6, lucide-react, Vite 5.

**Spec:** `docs/superpowers/specs/2026-10-28-tilapiers-final-design.md`

## Global Constraints

- No sensors, temperature, serial or notifications code remains (spec §2, §6 "Remove").
- Screening classes are exactly `Healthy`, `Aeromonas`, `TiLV`. UI wording is "signs consistent with …", never a diagnosis.
- Statuses: fish/pond health `Normal | Watch | Refer to technician`; readiness `Not Ready | Approaching | Ready | Size reached - health review needed`. A pond is `Ready` only when its health is `Normal`.
- Every cutoff lives in `Thresholds`, is editable by the admin, is saved with a timestamp in the `threshold_history` table, and is flagged `provisional` until `confirmed_with_technician` is true.
- Defaults: det_conf 0.25, referral_conf 0.50, K range 0.9–2.0, pond Watch ≥ 10 % W/R, pond Refer ≥ 1 Refer fish or ≥ 30 % W/R, target 300 g, Approaching share 0.50, Ready share 0.80, max CV 0.25, min SGR 0.5 %/day, culture 120–180 days, poly growth from 5 rounds, LW a = 0.0141 and b = 3.0, board inner size 38.0 × 26.0 cm (A3 minus margins), weight-fit min 10 fish.
- No fabricated measurements. Without a scale, L, A, W and K are `None` and shown as "No scale: not measured". Demo-seeded rows carry `source='demo'`.
- Model weights path comes from `TILAPIERS_YOLO_WEIGHTS` (default `backend/models/yolov8s_best.pt`). If the weights are missing, screening returns `None` with an "unavailable" reason, never a fake class.

## Review Focus

1. A photo where only 3 markers are visible in board mode → fails the quality check with reason "marker missing", and the fish isn't processed (test in Task 3).
2. A fish with only side A uploaded → still processed from one side; results show "1 of 2 photos" (test in Task 5).
3. A round with zero processed fish completed → statuses are "Insufficient data", with no crash and no Ready (test in Task 4).
4. Cutoff edits after a round is completed → the completed round's snapshot doesn't change (test in Task 6).
5. A caretaker calling admin endpoints → 403 (test in Task 6).

---

### Task 1: Clean out the sensor build, set up config, deps and model

**Files:**
- Delete: `backend/tilapiers/sensors/`, `monitor.py`, `notify.py`, `rules/environment.py`, `vision/indicators.py`, `vision/detector.py`, `firmware/`, the old tests for those
- Modify: `backend/requirements.txt` (add `opencv-python-headless`, `ultralytics`, `itsdangerous`; drop `pyserial`), `backend/tilapiers/config.py` (drop sensor/SMTP fields; add `yolo_weights` default, `seg_weights`, `secret_key`), `.env.example`, `.gitignore` (allow `backend/models/*.pt` to be ignored but keep `backend/models/README.md`)
- Create: `backend/models/` (copy `yolov8s_best.pt`), `backend/models/benchmarks/` (copy results.csv, args.yaml, confusion matrices, PR curve)

- [ ] Copy the model and benchmark artifacts; confirm `YOLO(path).names == {0:'Healthy',1:'Aeromonas',2:'TiLV'}`.
- [ ] Commit.

### Task 2: Rules: thresholds, health, weight, harvest, evaluation

**Files:** `backend/tilapiers/rules/{thresholds,health,weight,harvest,evaluation}.py`; tests `backend/tests/test_rules_*.py`

**Interfaces (Produces):**
- `Thresholds` dataclass with the fields from Global Constraints (`det_conf, referral_conf, k_min, k_max, pond_watch_share, pond_refer_share, target_weight_g, approaching_share, ready_share, max_cv, min_sgr, culture_days_min, culture_days_max, growth_poly_min_rounds, lw_a, lw_b, board_width_cm, board_height_cm, weight_fit_min_fish`), plus `to_dict/from_dict`, `GROUPS`, `LABELS`.
- `health.condition_factor(w, l) -> float|None`; `health.fish_status(cls, conf, k, t) -> {"status", "reasons":[str]}`; `health.pond_status(fish_statuses:list[str], t) -> {"status","watch_share","refer_count","n"}`.
- `weight.predict(model:dict, L, A) -> float|None`; `weight.provisional_model(t) -> dict` (kind `power`); `weight.fit_models(rows:[{L,A,W,group}], t) -> {"linear":{...},"poly":{...},"selected":"linear"|"poly","metrics":{...}}` with backward elimination (drop the term with the max p-value > 0.05, or else the smallest |t|) and grouped CV metrics `r2, rmse, mae, mare, mxae, mxre`.
- `harvest.sgr(w1,w2,days)`, `harvest.size_stats(weights,t)`, `harvest.growth_trend(points,t)` (keep the existing behavior), `harvest.readiness(weights, mean_k, doc, growth, pond_health, t) -> {"status","criteria":[{key,label,value,target,passed}],"met":int,"size":{...},"notes":[...]}`.
- `evaluation.agreement(pairs, labels) -> {"n","accuracy","kappa_w","matrix","labels"}` (linear weights); `evaluation.refer_recall(pairs)`; `evaluation.error_stats(pairs)` (MAE, RMSE, MARE).

- [ ] Write tests:
  - `fish_status('Healthy',0.9,1.2)` → Normal
  - `('Healthy',0.9,0.8)` → Watch
  - `('Healthy',0.9,None)` → Normal with reason "K not measured"
  - `('TiLV',0.4,1.2)` → Watch
  - `('Aeromonas',0.5,1.2)` → Refer (boundary is inclusive)
  - `pond_status` for 1 Refer of 20 → Refer; 2 Watch of 20 → Watch (10 %); 1 Watch of 20 → Normal
  - `readiness` with all five met and health Normal → Ready; health Watch → "Size reached - health review needed"; share 0.6 with 3 met → Approaching; empty weights → "Insufficient data"
  - `fit_models` on synthetic W = 0.015·L³ data gives selected-model R² > 0.95
  - `kappa_w` on a perfect agreement = 1.0
- [ ] Run `pytest backend/tests -q` → the new tests fail. Implement. Run → pass. Commit.

### Task 3: Vision: quality, board, outline

**Files:** `backend/tilapiers/vision/{quality,board,outline}.py`, `backend/tilapiers/vision/board_sheet.py` (printable board PNG/PDF); test `backend/tests/test_vision.py` (synthetic images drawn with cv2)

**Interfaces:**
- `quality.assess(img_bgr) -> {"sharpness","glare_share","exposure","ok","reasons":[...]}` (thresholds: sharpness ≥ 60, glare ≤ 0.08).
- `board.detect(img_bgr, width_cm, height_cm) -> {"found":[ids],"ok":bool,"warped":ndarray|None,"cm_per_px":float|None,"reasons":[...]}`. ArUco `DICT_4X4_50`, IDs 0 = TL, 1 = TR, 2 = BR, 3 = BL. Use each marker's inner corner, then warp to `px_per_cm = 20`.
- `board_sheet.render_png(width_cm, height_cm, dpi=150) -> bytes`.
- `outline.measure(warped_bgr, cm_per_px, seed_box=None, seg_model=None) -> {"ok","length_cm","area_cm2","mask_poly":[[x,y]],"bbox":[x1,y1,x2,y2],"method":"classical"|"yolo-seg","touches_edge":bool}`. Classical: GrabCut seeded by the box (or by the board centre minus a margin), with Otsu fallback. Largest contour. Length is the max pairwise distance on the convex hull.

- [ ] Tests:
  - Render the board sheet, paste a dark ellipse of 20 × 6 cm, apply a perspective warp, and confirm `board.detect` finds all 4 markers and `outline.measure` gives a length within ±5 % of 20 cm.
  - Cover one marker → `ok` is False with reason containing "marker".
  - A blurred image → quality reason "blurry".
- [ ] Implement, pass, commit.

### Task 4: Screening and per-fish pipeline

**Files:** `backend/tilapiers/vision/{screening,pipeline}.py`; test `backend/tests/test_pipeline.py`

**Interfaces:**
- `screening.Screener(weights_path)` with `.available`, `.name`, `.predict(img_bgr, conf) -> [{"cls","conf","box"}]`. `screening.load(settings)`. A `FakeScreener(results)` for tests lives in `tests/conftest.py`, never in the app.
- `pipeline.process_photo(path, board_mode, t, screener, seg) -> PhotoResult` (dict: `quality, board, outline, detections, top:{cls,conf}|None, annotated_path, ok, reasons`).
- `pipeline.merge_sides(results:list[PhotoResult]) -> {"cls","conf","length_cm","area_cm2","sides":n}` (spec call 7).
- [ ] Tests:
  - merge: (Healthy 0.9, TiLV 0.6) → TiLV 0.6; (Healthy 0.7, Healthy 0.9) → Healthy 0.9; lengths are averaged
  - a no-board photo gives `length_cm` None
- [ ] Implement, pass, commit.

### Task 5: DB schema and services

**Files:** rewrite `backend/tilapiers/db.py`, `backend/tilapiers/services.py`; test `backend/tests/test_services.py`

**Schema:**
- `users(id, username UNIQUE, full_name, role, pw_hash, active, created_at)`
- `ponds(id, name, location, setup, stocked_at, stocked_count, archived, created_at)`
- `settings(key, value_json)`, `threshold_history(id, ts, user, changes_json, confirmed)`
- `weight_models(id, created_at, kind, model_json, metrics_json, active)`
- `rounds(id, pond_id, sampled_at, days_of_culture, fish_count_n, board_mode, capture_condition, notes, status draft|completed, snapshot_json, tech_health, tech_readiness, created_by, created_at, source)`
- `fish(id, round_id, code, scale_weight_g, ruler_length_cm, cls, conf, length_cm, area_cm2, est_weight_g, k, status, reasons_json, tech_signs, tech_note, reviewed_by, reviewed_at, source)`
- `photos(id, fish_id, side A|B, path, annotated_path, ok, result_json, created_at)`
- `content(key, title, body_md)` for FAQs and About

**Services (Produces):** `create_round`, `add_fish`, `upload_photo(fish_id, side, bytes) -> photo` (runs the pipeline right away so the retake can happen on the spot), `process_fish(fish_id)`, `round_assessment(round_id) -> {health, readiness, summary:{n, avg_w, biomass, cv, share_at_target, mean_k}, growth}`, `complete_round` (stores the snapshot), `pond_overview`, `review_fish`, `set_pond_assessment`, `update_thresholds`, `fit_weight_model`, `evaluation()`, `export_csv(kind)`, `backup_zip()`, `restore_zip(bytes)`.

- [ ] Tests (temp dir DB, FakeScreener, synthetic board image):
  - create pond → round → fish → upload side A → fish has cls and length
  - `complete_round` then `update_thresholds` → snapshot unchanged
  - an empty completed round → Insufficient data
- [ ] Implement, pass, commit.

### Task 6: Auth and API

**Files:** `backend/tilapiers/auth.py` (PBKDF2-SHA256 200k iterations, itsdangerous signed cookie `tl_session`, 12 h), rewrite `backend/tilapiers/api.py`, `main.py`; test `backend/tests/test_api.py`

**Routes (all under `/api`):**
- `auth/login|logout|me`, `profile/password`
- `ponds` CRUD (admin writes)
- `ponds/{id}` overview
- `rounds` POST (caretaker/admin); `rounds/{id}` GET; `rounds/{id}/fish` POST; `fish/{id}` PATCH (scale W, ruler L); `fish/{id}/photos/{side}` POST multipart; `rounds/{id}/complete` POST
- `review/queue`, `fish/{id}/review` (technician), `rounds/{id}/assessment` (technician)
- `thresholds` GET/PUT (admin), `thresholds/history`
- `weight-model` GET, `weight-model/fit` POST (admin)
- `evaluation`, `export/{kind}.csv`
- `users` CRUD (admin)
- `backup` GET, `restore` POST (admin)
- `content/{key}` GET/PUT
- `board.png`, `photos/{id}/{raw|annotated}`
- `system` (model name, availability, benchmarks, demo flag)

- [ ] Tests: login ok and bad; a caretaker PUTting `/api/thresholds` gets 403; an anonymous GET of `/api/ponds` gets 401; the full upload flow through the API with FakeScreener.
- [ ] Implement, pass, commit.

### Task 7: Demo seed and run script

**Files:** rewrite `backend/tilapiers/seed.py`, `run-demo.ps1`, `README.md`, `docs/ARCHITECTURE.md`

- [ ] Seed: 3 users, FAQ/About content, 2 ponds (Pond A at DOC 30/60/90/120/150, Pond B at 30/60/90/110), 20 fish per round with `source='demo'`, weights from logistic growth with 15–25 % CV, two Aeromonas fish in Pond B's latest round. Expected: Pond A Ready, Pond B Approaching with health Watch or Refer.
- [ ] Test: a seeded DB has `pond_overview` statuses as expected. Commit.

### Task 8: Frontend: shell, auth, design system (ui-ux-pro-max)

**Files:** `frontend/src/main.jsx`, `lib/{api,auth,format}.js`, `components/{Shell,ui,Status,charts}.jsx`, `styles.css`, `pages/Login.jsx`, `pages/Profile.jsx`

- [ ] Role-aware navigation:
  - Caretaker: Dashboard, Sample, History, FAQs
  - Technician: Dashboard, Review, Evaluation
  - Admin: everything plus Maintenance
- [ ] A 401 redirects to /login. Status badges use icon + text + color.
- [ ] `npx vite build` passes. Commit.

### Task 9: Frontend: caretaker flow

**Files:** `pages/{Dashboard,Pond,NewRound,Capture,RoundResults}.jsx`

- [ ] Capture: a fish list. Per fish: Side A/B `<input type=file accept=image/* capture=environment>`, a quality result chip, a Retake button, and scale W / ruler L inputs. The page shows a running summary, and "Complete round" asks for confirmation.
- [ ] Results: per-fish annotated thumbnail, class with confidence, L, A, W, K, status; health and readiness panels with their criteria; average weight and biomass; disclaimers.
- [ ] Build passes. Commit.

### Task 10: Frontend: technician, admin, evaluation, content

**Files:** `pages/{Review,Maintenance,Evaluation,Faqs,About}.jsx`

- [ ] Maintenance tabs: Ponds, Users, Cutoffs (with history and a "confirmed with technician" toggle), Weight model (fit, then a comparison table), Board (size plus a print link), Backup/Restore.
- [ ] Evaluation:
  - Detector comparison (paper Tables 10 and 11, static) plus the live training curves from `benchmarks/results.csv`
  - Weight model (Table 12 format, live)
  - Status agreement (κ_w, matrix, Refer recall)
  - Length and weight error vs. ruler and scale
  - Retake rate
  - CSV exports
- [ ] Build passes. Commit.

### Task 11: End-to-end verification

- [ ] Run `pytest` → all pass.
- [ ] Start the demo. Log in as each role. Upload a real public-dataset image in no-board mode and a synthetic board photo; see the class, confidence and length. Complete the round. Check the dashboard statuses.
- [ ] Screenshot the key pages. Fix any defects. Commit.
