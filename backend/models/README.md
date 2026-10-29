# Models

- `yolov8s_best.pt` — screening detector trained by the study team
  (Ultralytics YOLOv8s, 100 epochs, 640 px, batch 16, seed 0, Colab T4), 22 MB.
  Training labels: `0 Healthy`, `1 Aeromonas`, `2 TiLV`. The app shows them as visible defects,
  not diseases: Healthy → *No visible defect*, TiLV → *Skin erosion*, Aeromonas → *Red sores*
  (`DEFECT_OF_LABEL` in `tilapiers/vision/screening.py`).
- `benchmarks/` — the training run's `results.csv`, `args.yaml`, curves and confusion
  matrices. The Evaluation page reads them.

To use YOLO26s instead, set `TILAPIERS_YOLO_WEIGHTS` in `backend/.env`.
A segmentation model for the fish outline goes in `TILAPIERS_SEG_WEIGHTS`.
