from ultralytics import YOLO

# Load YOLOv8 nano - smallest and fastest, good for MVP
model = YOLO("yolov8n.pt")

# Train on the fish dataset
results = model.train(
    data="aquarium-qlnqy/data.yaml",  # path to your dataset
    epochs=50,                        # 50 rounds of training
    imgsz=640,                        # image size
    batch=8,                          # lower this to 4 if you get memory errors
    name="tilapiers_fish",             # folder name for results
    patience=10,                      # stop early if no improvement
    device="cpu",                     # use "0" if you have an NVIDIA GPU
)

print("Training complete!")
print("Best model saved at: runs/detect/tilapiers_fish/weights/best.pt")
