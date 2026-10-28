# Models

- `yolov8s_best.pt` — disease screening detector trained by the study team
  (Ultralytics YOLOv8s, 100 epochs, 640 px, batch 16, seed 0, Colab T4).
  Classes: `0 Healthy`, `1 Aeromonas`, `2 TiLV`. Not committed (22 MB) — copy it here.
- `benchmarks/` — the training run's `results.csv`, `args.yaml`, curves and confusion
  matrices. The Evaluation page reads them.

To use YOLO26s instead, set `TILAPIERS_YOLO_WEIGHTS` in `backend/.env`.
A segmentation model for the fish outline goes in `TILAPIERS_SEG_WEIGHTS`.
