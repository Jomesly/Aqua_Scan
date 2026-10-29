# Demo photos

Public tilapia photos for showing defect screening without a sampling board. Create the round with
**Public / test photos (no board)**, add one fish per pair, and upload Side A and Side B.

| Fish | Expected screening | Expected Health status |
|---|---|---|
| fish1, fish2 | Skin erosion | Refer to technician |
| fish3, fish4 | Red sores | Refer to technician |
| fish5, fish6 | No visible defect | Normal |

Each photo was checked through the app's pipeline with `yolov8s_best.pt` on 2026-10-28 (confidence 72–97 %).

These photos come from a public dataset that may overlap the model's training data, so they show that the
system works, not how accurate it is. For accuracy, use the Evaluation page (paper Tables 10 and 11).

Source: "Tilapia Skin Disease" by inchang, Roboflow Universe,
https://universe.roboflow.com/inchang/tilapia-skin-disease-e3eov — licensed CC BY 4.0. Files renamed; not modified.
