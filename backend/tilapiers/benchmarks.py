"""Detector benchmarks shown on the Evaluation page.

``PAPER_TABLE_10`` and ``PAPER_TABLE_11`` are copied from the study (Chapter 3,
Design Trade-offs): one run per model, 100 epochs, 640 px, batch 16, seed 0, Colab
T4, tested on 33 held-out unique photographs. The training curve comes from the
team's own ``results.csv`` in backend/models/benchmarks.
"""

import csv
from pathlib import Path

PAPER_TABLE_10 = {
    "models": ["YOLOv8s", "YOLO11s", "YOLO26s"],
    "rows": [
        ("Precision", [0.897, 0.748, 0.904], "max"),
        ("Recall", [0.675, 0.612, 0.594], "max"),
        ("F1-score", [0.770, 0.673, 0.717], "max"),
        ("mAP50", [0.683, 0.637, 0.641], "max"),
        ("mAP50-95", [0.470, 0.406, 0.440], "max"),
        ("AP50, Healthy", [0.995, 0.984, 0.995], "max"),
        ("AP50, Aeromonas", [0.302, 0.298, 0.260], "max"),
        ("AP50, TiLV", [0.751, 0.631, 0.667], "max"),
        ("CPU time per image (ms)", [294.7, 265.6, 259.1], "min"),
        ("Model size (MB)", [22.5, 19.2, 20.3], "min"),
    ],
    "note": "One training run per model (100 epochs, 640 px, batch 16, seed 0) on Google Colab with an NVIDIA T4, "
            "tested on 33 held-out unique photographs.",
}

PAPER_TABLE_11 = {
    "models": ["YOLOv8s", "YOLO11s", "YOLO26s"],
    "rows": [
        ("Balanced (0.25 / 0.25 / 0.25 / 0.25)", [0.968, 0.911, 0.955]),
        ("Precision focus (0.40 / 0.20 / 0.20 / 0.20)", [0.973, 0.894, 0.964]),
        ("Recall focus (0.20 / 0.40 / 0.20 / 0.20)", [0.974, 0.910, 0.940]),
        ("mAP50 focus (0.20 / 0.20 / 0.40 / 0.20)", [0.974, 0.915, 0.951]),
        ("CPU speed focus (0.20 / 0.20 / 0.20 / 0.40)", [0.950, 0.924, 0.964]),
    ],
}

IMAGES = ["confusion_matrix_normalized.png", "BoxPR_curve.png", "BoxF1_curve.png", "results.png",
          "val_batch0_pred.jpg"]


def _training_curve(path):
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as f:
        rows = [{k.strip(): v.strip() for k, v in r.items()} for r in csv.DictReader(f)]
    pick = {"epoch": "epoch", "precision": "metrics/precision(B)", "recall": "metrics/recall(B)",
            "map50": "metrics/mAP50(B)", "map50_95": "metrics/mAP50-95(B)",
            "train_box_loss": "train/box_loss", "val_box_loss": "val/box_loss"}
    out = []
    for r in rows:
        try:
            out.append({k: float(r[v]) for k, v in pick.items()})
        except (KeyError, ValueError):
            continue
    return out


def load_benchmarks(directory, screener_info):
    d = Path(directory)
    curve = _training_curve(d / "results.csv")
    best = max(curve, key=lambda r: r["map50_95"] * 0.9 + r["map50"] * 0.1) if curve else None
    return {"table10": PAPER_TABLE_10, "table11": PAPER_TABLE_11, "curve": curve, "best_epoch": best,
            "final_epoch": curve[-1] if curve else None,
            "images": [n for n in IMAGES if (d / n).exists()], "deployed": screener_info}
