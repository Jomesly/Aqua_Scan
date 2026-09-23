import cv2
from detection_core import Calibration, annotate_frame, detect_fish, load_model, open_camera


calibration = Calibration()
model = load_model()


cap = open_camera()

if cap is None:
    print("ERROR: Cannot open webcam")
    print("Close other camera apps, check Windows camera permissions, then try again.")
    exit()

print("Tilapiers detection running — press Q to quit")
print(
    "Calibration: "
    f"fish-only, confidence >= {calibration.confidence}, "
    f"box area {calibration.min_box_area_ratio:.1%}-{calibration.max_box_area_ratio:.0%}"
)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    result = detect_fish(frame, model, calibration)
    annotated_frame, _ = annotate_frame(frame, result, calibration)

    cv2.imshow("Tilapiers — Fish Detection", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
