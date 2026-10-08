import glob, os
from ultralytics import YOLO

for f in sorted(glob.glob("models/**/*.pt", recursive=True)):
    m = YOLO(f)
    ck = m.ckpt or {}
    ta = ck.get("train_args", {})
    print(f, "|", round(os.path.getsize(f) / 1e6, 1), "MB |", len(m.names), "classes |",
          "data:", ta.get("data"), "| epochs:", ta.get("epochs"), "| date:", ck.get("date"))