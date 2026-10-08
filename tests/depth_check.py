import sys
from transformers import pipeline
from PIL import Image

pipe = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Metric-Outdoor-Small-hf")
img = Image.open(sys.argv[1]).convert("RGB")
d = pipe(img)["predicted_depth"]
h, w = d.shape
print("depth shape", tuple(d.shape), "| image size (w,h)", img.size)
print("near (road just ahead, bottom center):", d[int(h*.9):, int(w*.4):int(w*.6)].median().item())
print("far  (sky, top center):               ", d[:int(h*.2), int(w*.4):int(w*.6)].median().item())