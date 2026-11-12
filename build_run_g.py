import collections, csv, json, os, random, shutil, sys, zipfile
sys.path.insert(0, "/content")
from ls_to_yolo import load_class_names
from outside_to_yolo import (load_arts, load_streetview, cap_photos, remap_labels,
                             make_alias_ids, ARTS_TO_OURS)
from run_g_classes import RENAME

DRIVE = "/content/drive/MyDrive/ladot_v2_runs"
PARTS = f"{DRIVE}/run_f"                      # footage_f.zip and roboflow_f.zip from Run F
SV_ZIP = f"{DRIVE}/dataset_v1.zip"
CONFIG_F = "/content/label_config_F.xml"      # the 54 names the footage/Roboflow labels use
CONFIG_G = "/content/label_config_G.xml"      # the 40 names Run G trains on
ARTS = "/content/arts/challenging"
WORK = "/content/g_work"
OUT = "/content/run_g"
CAP = 300
SV_CAP = 200
N_SV_VAL = 100
BUILD = "--build" in sys.argv

old_list = load_class_names(CONFIG_F)
old_by_num = {i: n for i, n in enumerate(old_list)}
names = load_class_names(CONFIG_G)
ids = {n: i for i, n in enumerate(names)}
assert len(old_list) == 54, f"expected 54 old classes, found {len(old_list)}"
assert len(names) == 40, f"expected 40 classes, found {len(names)}"
alias = make_alias_ids(names, RENAME)         # old names -> new class numbers

SV_CLASS_CAPS = {ids["Stop Signs 1022"]: 600,          # lets All-Way photos in
                 ids["Street Cleaning Symbol"]: 400,   # five classes merged into one
                 ids["Speed Hump Sign"]: 300}          # five classes merged into one

ARTS_CODE_MAP = dict(ARTS_TO_OURS)
ARTS_CODE_MAP["R4-7"] = "R4-7 Keep Right Arrow"

if BUILD and os.path.exists(OUT):
    sys.exit(f"{OUT} already exists. Run: rm -rf {OUT}   then try again.")
if not os.path.isdir(f"{ARTS}/Annotations"):
    sys.exit("ARTS Challenging is not extracted. Extract it first (the tar command from before).")

# 1. Unzip everything into a scratch folder (safe to delete and redo)
shutil.rmtree(WORK, ignore_errors=True)
for tag, zp in (("footage", f"{PARTS}/footage_f.zip"),
                ("roboflow", f"{PARTS}/roboflow_f.zip"),
                ("sv", SV_ZIP)):
    with zipfile.ZipFile(zp) as z:
        z.extractall(f"{WORK}/{tag}")
    print("unzipped", tag)

def read_lines(path):
    return [l.strip() for l in open(path).read().splitlines() if l.strip()]

def to_g(lines):
    """Run F numbering -> Run G numbering, by NAME. Stops on a name that has no home."""
    return remap_labels("\n".join(lines), old_by_num, alias)

def class_counts(items):
    c = collections.Counter()
    for it in items:
        for l in it["lines"]:
            c[int(l.split()[0])] += 1
    return c

# 2. Footage (review letters already applied). Keep its own train/val split.
foot = {"train": [], "val": []}
for split in ("train", "val"):
    ldir = f"{WORK}/footage/labels/{split}"
    for f in sorted(os.listdir(ldir)):
        stem = f[:-4]
        pic = [p for p in os.listdir(f"{WORK}/footage/images/{split}") if os.path.splitext(p)[0] == stem]
        assert len(pic) == 1, f"footage picture problem for {stem}: {pic}"
        foot[split].append({"name": pic[0], "src": f"{WORK}/footage/images/{split}/{pic[0]}",
                            "lines": to_g(read_lines(f"{ldir}/{f}")), "src_tag": "footage"})

# 3. Roboflow (already capped on the computer). All go to train.
rf = []
for f in sorted(os.listdir(f"{WORK}/roboflow/labels")):
    stem = f[:-4]
    rf.append({"name": stem + ".jpg", "src": f"{WORK}/roboflow/images/{stem}.jpg",
               "lines": to_g(read_lines(f"{WORK}/roboflow/labels/{f}")), "src_tag": "roboflow"})

totals = class_counts(foot["train"] + foot["val"])
totals.update(class_counts(rf))

# 4. ARTS Challenging: keep only fully mapped photos, then cap
arts_all, arts_rep = load_arts(ARTS, alias, code_map=ARTS_CODE_MAP)
arts, totals = cap_photos(arts_all, CAP, base_counts=totals)
for it in arts:
    it["src_tag"] = "arts"
print("ARTS photos: mapped", len(arts_all), "| after cap", len(arts))

# 5. Street View train: remap by name, cap (empty pictures can't be capped, so keep them)
sv_all, sv_rep = load_streetview(f"{WORK}/sv", alias, split="train")
sv_empty = [i for i in sv_all if not i["lines"]]
sv_boxed = [i for i in sv_all if i["lines"]]
sv_kept, totals = cap_photos(sv_boxed, SV_CAP, base_counts=totals, class_caps=SV_CLASS_CAPS)
sv_train = sv_kept + sv_empty
for it in sv_train:
    it["src_tag"] = "streetview"
print("Street View train:", sv_rep, "| with boxes", len(sv_boxed),
      "| kept after cap", len(sv_kept), "| empty kept", len(sv_empty))

# 6. Validation = footage val + 100 random Street View val images (seed 0)
sv_val_all, _ = load_streetview(f"{WORK}/sv", alias, split="val")
sv_val_all.sort(key=lambda i: i["name"])
sv_val = random.Random(0).sample(sv_val_all, N_SV_VAL)
for it in sv_val:
    it["src_tag"] = "streetview"

train = foot["train"] + rf + arts + sv_train
val = foot["val"] + sv_val

# 7. Safety checks
problems = []
for n, c in collections.Counter(it["name"] for it in train + val).items():
    if c > 1:
        problems.append(f"duplicate file name: {n}")
for it in train + val:
    for l in it["lines"]:
        p = l.split()
        if len(p) != 5 or not (0 <= int(p[0]) < len(names)):
            problems.append(f"bad label in {it['name']}: {l}")
        elif not all(0 <= float(v) <= 1 for v in p[1:]):
            problems.append(f"number outside 0..1 in {it['name']}: {l}")
    if not os.path.exists(it["src"]):
        problems.append(f"missing picture: {it['src']}")
if problems:
    print(f"\nSTOPPING: {len(problems)} problem(s):")
    for p in problems[:30]:
        print("  -", p)
    sys.exit(1)

# 8. Audit
by_src = collections.Counter(it["src_tag"] for it in train)
print("\nTRAIN images by source:", dict(by_src), "| total", len(train))
print("VAL images:", len(val), "| total images:", len(train) + len(val))
print(f"Street View share of train images: {by_src['streetview'] / len(train):.0%}")
tc, vc = class_counts(train), class_counts(val)
print("\nboxes per class (train / val):")
for i, n in enumerate(names):
    print(f"  {i:>2} {n}: {tc[i]} / {vc[i]}")
print("classes with zero train boxes:", [names[i] for i in range(len(names)) if tc[i] == 0])
print("classes under 30 train boxes:", [f"{names[i]} ({tc[i]})" for i in range(len(names)) if 0 < tc[i] < 30])

if not BUILD:
    print("\nAUDIT ONLY: nothing written. Add --build to write the dataset.")
    sys.exit(0)

# 9. Build
for sp in ("train", "val"):
    os.makedirs(f"{OUT}/images/{sp}")
    os.makedirs(f"{OUT}/labels/{sp}")
for sp, items in (("train", train), ("val", val)):
    for it in items:
        shutil.copy2(it["src"], f"{OUT}/images/{sp}/{it['name']}")
        stem = os.path.splitext(it["name"])[0]
        with open(f"{OUT}/labels/{sp}/{stem}.txt", "w") as f:
            f.write("\n".join(it["lines"]) + ("\n" if it["lines"] else ""))
with open(f"{OUT}/data.yaml", "w") as f:
    f.write(f"path: {OUT}\ntrain: images/train\nval: images/val\nnames:\n")
    for i, n in enumerate(names):
        f.write(f"  {i}: {json.dumps(n)}\n")
with open(f"{OUT}/manifest.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["name", "source", "split", "boxes"])
    for sp, items in (("train", train), ("val", val)):
        for it in items:
            w.writerow([it["name"], it["src_tag"], sp, len(it["lines"])])
print(f"\nBUILT {len(train) + len(val)} images into {OUT}")