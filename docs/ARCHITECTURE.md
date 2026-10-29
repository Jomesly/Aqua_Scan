# Architecture

```
 Sampling station                 Server (laptop / BFAR PC)                                   Browser
┌──────────────────────┐        ┌─────────────────────────────────────────────────────────┐  ┌──────────────────────┐
│ phone on a stand      │ photo  │ api.py ─ auth.py (session cookie, 3 roles)              │  │ React SPA            │
│ board + 4 ArUco marks │───────►│   │                                                     │  │ caretaker: dashboard,│
│ facility scale, ruler │ W, L   │ services.py                                             │◄►│  sampling, results   │
└──────────────────────┘        │   ├─ vision/pipeline.py  (per photo)                     │  │ technician: review,  │
                                 │   │    quality → board (markers, homography, cm/px)     │  │  evaluation          │
                                 │   │    → outline (length, area) → crop → screening      │  │ admin: maintenance   │
                                 │   │    → annotated photo; merge_sides (both photos)     │  └──────────────────────┘
                                 │   ├─ rules/  pure, unit-tested                          │
                                 │   │    weight (OLS, backward elimination, grouped CV)   │
                                 │   │    health (K, fish and pond status)                 │
                                 │   │    harvest (size, CV, SGR, degree-2 growth, ready)  │
                                 │   │    evaluation (κ_w, Refer recall, error stats)      │
                                 │   └─ db.py  SQLite (WAL) + uploads/                     │
                                 └─────────────────────────────────────────────────────────┘
```

## Per-photo pipeline (paper Figures 4, 9 and 10)

1. **Quality** (`vision/quality.py`): sharpness (Laplacian variance ≥ 60), exposure (mean 50–215) and glare (≤ 8 % blown-out pixels). A failure is returned at once with the reason, so the caretaker can retake the photo while the fish is still on the board. Every failure counts toward the retake rate.
2. **Board** (`vision/board.py`): finds the ArUco `DICT_4X4_50` markers with ids 0–3 (TL, TR, BR, BL). Each marker's inner corner maps to the known inner rectangle, and the homography produces a flat view at 20 px/cm. A missing marker is a failure, with the missing corner named. Skipped in *no-board* rounds (public or test photos).
3. **Outline** (`vision/outline.py`): YOLO-seg if `TILAPIERS_SEG_WEIGHTS` is set. Otherwise it uses classical segmentation: Lab color distance from the board, Otsu threshold, then morphology. Length is the longest line across the convex hull, and area is the contour area. A fish touching the edge (tail cut off) fails.
4. **Screening** (`vision/screening.py`): Ultralytics detect weights trained with the labels Healthy, Aeromonas and TiLV, run on the fish crop. The labels are translated right after the model into visible defects (No visible defect, Skin erosion, Red sores); nothing downstream names a disease. Detections below `det_conf` are discarded. An unavailable model means "not screened", never a made-up class.
5. **Merge** (`pipeline.merge_sides`): length and area are the means of both sides. The class is the disease class with the higher confidence if either side shows one (paper Step 10).

## Per-fish and per-round rules (paper Figure 11)

- Weight: `predict(active model, L, A)`. The provisional power curve is used until a fit exists. The fitted model is the one selected by grouped CV (the degree-2 model must beat linear by at least 5 % RMSE).
- K = 100·W/L³ from the **estimated** values (paper: computed the same way at testing and use).
- Fish status: No visible defect with K in range is Normal. Low or high K, or a defect below the referral cutoff, is Watch. A defect at or above the referral cutoff is Refer.
- Pond health: any Refer fish, or a Watch/Refer share of at least `pond_refer_share`, gives Refer. A share of at least `pond_watch_share` gives Watch.
- Readiness: five indicators (share at target ≥ Ready share, CV ≤ max, growth, mean K in range, DOC ≥ usual start). All met with Normal health gives Ready; all met with any other health gives "Size reached - health review needed". A share at least the Approaching share with 3 or more indicators met gives Approaching. Otherwise the pond is Not Ready.
- Growth: overall SGR over the completed rounds. With 5 or more rounds, a degree-2 curve over the observed days only.

Completing a round stores an **assessment snapshot**, so later changes to the cutoffs or the model don't rewrite history. Draft rounds recompute live.

## Data

`users`, `ponds`, `rounds` (draft/completed, snapshot, technician assessments), `fish` (scale W, ruler L, class, conf, L, A, est W, K, status, technician signs), `photos` (side, current flag for retakes, pipeline result), `weight_models` (fit results, active flag), `settings` (cutoffs, confirmed flag), `threshold_history`, `content` (FAQs, About Us). Demo rows carry `source='demo'`.
