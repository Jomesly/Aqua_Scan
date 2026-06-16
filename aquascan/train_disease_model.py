import argparse
from pathlib import Path

from ultralytics import YOLO


ROOT_DIR = Path(__file__).resolve().parent
DATASETS = {
    "wound": ROOT_DIR / "datasets" / "fish_disease_detection.yaml",
    "tilapia": ROOT_DIR / "datasets" / "fish_disease_tilapia_fixed.yaml",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Train AquaScan disease detection models.")
    parser.add_argument("--dataset", choices=DATASETS.keys(), default="wound")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def main():
    args = parse_args()
    data_path = DATASETS[args.dataset]
    run_name = f"aquascan_{args.dataset}_disease"

    if not data_path.exists():
        raise FileNotFoundError(f"Dataset config not found: {data_path}")

    model = YOLO(str(ROOT_DIR / "yolov8n.pt"))
    model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        name=run_name,
        patience=8,
        device=args.device,
        project=str(ROOT_DIR / "runs" / "detect"),
    )

    best_path = ROOT_DIR / "runs" / "detect" / run_name / "weights" / "best.pt"
    print("Training complete")
    print(f"Best model saved at: {best_path}")


if __name__ == "__main__":
    main()
