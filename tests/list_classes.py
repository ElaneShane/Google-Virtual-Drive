from ultralytics import YOLO
import glob

for f in sorted(glob.glob("models/**/*.pt", recursive=True)):
    print(f.split("/")[-1], "->", YOLO(f).names)