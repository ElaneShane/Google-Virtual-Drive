import json, os, re
from PIL import Image, ImageDraw

HOME = os.path.expanduser("~")
KEY = f"{HOME}/Google-Virtual-Drive/uncomitted/answer_key/FROZEN_answer_key_oct26.json"
FRAMES = f"{HOME}/Google-Virtual-Drive/uncomitted/answer_key/frames"
OUT = f"{HOME}/Google-Virtual-Drive/uncomitted/key_check"
os.makedirs(OUT, exist_ok=True)
WANT = {"7th_NB_049", "7th_NB_051", "7th_NB_052", "7th_SB_058", "7th_SB_085"}

for t in json.load(open(KEY)):
    stem = re.sub(r"^[0-9a-f]{8}-", "", os.path.splitext(os.path.basename(t["data"]["image"]))[0])
    if stem not in WANT:
        continue
    anns = [a for a in t.get("annotations", []) if not a.get("was_cancelled")]
    img = Image.open(f"{FRAMES}/{stem}.jpg").convert("RGB")
    W, H = img.size
    d = ImageDraw.Draw(img)
    for n, r in enumerate(anns[-1]["result"]):
        v = r.get("value", {})
        if "rectanglelabels" not in v:
            continue
        x1, y1 = v["x"] / 100 * W, v["y"] / 100 * H
        x2, y2 = x1 + v["width"] / 100 * W, y1 + v["height"] / 100 * H
        name = v["rectanglelabels"][0]
        d.rectangle([x1, y1, x2, y2], outline="red", width=4)
        pad = 150
        crop = Image.open(f"{FRAMES}/{stem}.jpg").convert("RGB").crop(
            (max(0, x1 - pad), max(0, y1 - pad), min(W, x2 + pad), min(H, y2 + pad)))
        crop = crop.resize((crop.width * 3, crop.height * 3))
        crop.save(f"{OUT}/{stem}_{n}_{name.replace(' ', '_')}.jpg")
    img.save(f"{OUT}/{stem}_full.jpg")
print("saved to", OUT)