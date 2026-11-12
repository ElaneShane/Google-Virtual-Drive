import os
import random

# Roboflow class name -> our class name. None means "a light, not a sign we model: skip the box".
RF_TO_OURS = {
    "stop": "Stop Signs 1022",
    "do_not_enter": "Do Not Enter Sign",
    "no_left_turn": "No Left Turn",
    "no_u_turn": "No U-Turn",
    "no_left_turn_no_u_turn": "R3-18_No_U_Turn_or_Left_Turn",
    "speed_limit_25": "speed_limit_sign",
    "speed_limit_30": "speed_limit_sign",
    "speed_limit_35": "speed_limit_sign",
    "speed_limit_40": "speed_limit_sign",
    "speed_limit_45": "speed_limit_sign",
    "children_crossing": "School",
    "stop_ahead": "Stop Ahead",
    "left_turn_only": "Left Arrow with No U-Turn Text",
    "left_turn_u_turn": "Left Arrow and U-Turn Arrow",
    "greenLight": None,
    "orangeLight": None,
    "redLight": None,
}


def rf_source_key(filename):
    """Roboflow copies share everything before '.rf.'. That start identifies the source photo."""
    if ".rf." in filename:
        return filename.split(".rf.")[0]
    return os.path.splitext(filename)[0]


def pick_one_copy(filenames, seed=0):
    """{source photo: the one copy we keep}. Same input and seed always give the same answer."""
    groups = {}
    for f in filenames:
        groups.setdefault(rf_source_key(f), []).append(f)
    rng = random.Random(seed)
    return {key: rng.choice(sorted(files)) for key, files in sorted(groups.items())}


def convert_rf_lines(text, rf_names, class_ids):
    """Roboflow label text -> (our YOLO lines, number of light boxes skipped).
    Raises ValueError on a malformed line or a Roboflow class we have no rule for."""
    out, skipped = [], 0
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split()
        if len(parts) != 5:
            raise ValueError(f"expected 5 numbers per line, got: {raw!r}")
        try:
            idx = int(parts[0])
        except ValueError:
            raise ValueError(f"class number is not a whole number: {raw!r}")
        if idx < 0 or idx >= len(rf_names):
            raise ValueError(f"class number {idx} is outside the Roboflow class list")
        name = rf_names[idx]
        if name not in RF_TO_OURS:
            raise ValueError(f"no rule for Roboflow class: {name}")
        target = RF_TO_OURS[name]
        if target is None:
            skipped += 1
            continue
        if target not in class_ids:
            raise ValueError(f"our class list has no class named: {target}")
        out.append(f"{class_ids[target]} " + " ".join(parts[1:]))
    return out, skipped



def load_rf_names(yaml_path):
    """Read the names: [...] line from Roboflow's data.yaml (a one-line Python-style list)."""
    import ast
    for line in open(yaml_path, encoding="utf-8"):
        if line.startswith("names:"):
            names = ast.literal_eval(line.split(":", 1)[1].strip())
            if not isinstance(names, list) or not names:
                raise ValueError("names: line did not hold a list")
            return names
    raise ValueError("no names: line found in data.yaml")


def load_roboflow(root, class_ids, seed=0):
    """Walk train/valid/test. Returns (kept, report).
    kept = list of dicts: name, src (picture path), lines (our YOLO lines).
    A photo is dropped if it has no sign boxes left (for example it only had lights)."""
    rf_names = load_rf_names(os.path.join(root, "data.yaml"))
    kept = []
    report = {"photos_seen": 0, "unique_photos": 0, "dropped_no_signs": 0,
              "light_boxes_skipped": 0, "no_label_file": 0}
    for split in ("train", "valid", "test"):
        img_dir = os.path.join(root, split, "images")
        lbl_dir = os.path.join(root, split, "labels")
        if not os.path.isdir(img_dir):
            continue
        files = sorted(f for f in os.listdir(img_dir) if f.lower().endswith(".jpg"))
        report["photos_seen"] += len(files)
        picked = pick_one_copy(files, seed=seed)
        report["unique_photos"] += len(picked)
        for key, fname in picked.items():
            lbl = os.path.join(lbl_dir, os.path.splitext(fname)[0] + ".txt")
            if not os.path.exists(lbl):
                report["no_label_file"] += 1
                continue
            lines, skipped = convert_rf_lines(open(lbl).read(), rf_names, class_ids)
            report["light_boxes_skipped"] += skipped
            if not lines:
                report["dropped_no_signs"] += 1
                continue
            kept.append({"name": f"rf_{key}.jpg",
                         "src": os.path.join(img_dir, fname),
                         "lines": lines})
    return kept, report



import xml.etree.ElementTree as ET

# ARTS sign code -> our class name
ARTS_TO_OURS = {
    "R1-1": "Stop Signs 1022",
    "R5-1": "Do Not Enter Sign",
    "R3-2": "No Left Turn",
    "R3-4": "No U-Turn",
    "R8-3": "No Parking Signs Symbol",
    "R7-1": "No Parking Signs Letters",
    "W11-2": "Pedestrian Traffic, (Symbol) 572",
    "OM1-1": "Diamond Yellow Reflector 0215",
    "R6-1": "One Way with Arrow",
    "W16-7": "other_sign",
    "S1-1": "School",
    "R1-5": "Yield Here to Pedestrians",
    "R3-7": "Right Lane Must Turn Right",
    "R2-125": "speed_limit_sign",
    "R2-130": "speed_limit_sign",
    "R2-135": "speed_limit_sign",
    "R2-140": "speed_limit_sign",
    "R2-150": "speed_limit_sign",
    "R10-11": "No Turn on Red",
    "W17-1": "Speed humps -- W17-1",
    "R7-2": "No Parking Signs Symbol",
}


def convert_arts_xml(xml_text, class_ids, code_map=None):
    """ARTS Pascal VOC XML text -> (our YOLO lines, set of codes we have no rule for).
    The caller drops the photo if the set is not empty."""
    code_map = code_map or ARTS_TO_OURS
    root = ET.fromstring(xml_text)
    size = root.find("size")
    if size is None or size.find("width") is None or size.find("height") is None:
        raise ValueError("XML has no picture size")
    W, H = float(size.find("width").text), float(size.find("height").text)
    if W <= 0 or H <= 0:
        raise ValueError("picture size is not positive")
    lines, unmapped = [], set()
    for obj in root.findall("object"):
        code = obj.find("name").text.strip()
        if code not in code_map:
            unmapped.add(code)
            continue
        target = code_map[code]
        if target not in class_ids:
            raise ValueError(f"our class list has no class named: {target}")
        b = obj.find("bndbox")
        x1, y1, x2, y2 = (float(b.find(k).text) for k in ("xmin", "ymin", "xmax", "ymax"))
        x1, y1, x2, y2 = max(0.0, x1), max(0.0, y1), min(W, x2), min(H, y2)
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"box has no area for code {code}")
        lines.append(f"{class_ids[target]} {(x1 + x2) / 2 / W:.6f} {(y1 + y2) / 2 / H:.6f} "
                     f"{(x2 - x1) / W:.6f} {(y2 - y1) / H:.6f}")
    return lines, unmapped


import collections


def load_arts(root, class_ids, code_map=None):
    """Walk ARTS Annotations/ and JPEGImages/. Returns (kept, report).
    A photo is kept only if EVERY box maps to one of our classes."""
    ann_dir = os.path.join(root, "Annotations")
    img_dir = os.path.join(root, "JPEGImages")
    kept = []
    unmapped_counter = collections.Counter()
    report = {"xml_seen": 0, "bad_xml": 0, "dropped_unmapped": 0,
              "dropped_no_signs": 0, "missing_picture": 0}
    for f in sorted(os.listdir(ann_dir)):
        if not f.endswith(".xml"):
            continue
        report["xml_seen"] += 1
        stem = os.path.splitext(f)[0]
        text = open(os.path.join(ann_dir, f), encoding="utf-8").read()
        try:
            lines, unmapped = convert_arts_xml(text, class_ids, code_map)
            fn = ET.fromstring(text).find("filename")
        except (ValueError, ET.ParseError):
            report["bad_xml"] += 1
            continue
        if unmapped:
            report["dropped_unmapped"] += 1
            unmapped_counter.update(unmapped)   # counts photos each code appears in
            continue
        if not lines:
            report["dropped_no_signs"] += 1
            continue
        pic = fn.text.strip() if fn is not None and fn.text else stem + ".jpg"
        src = os.path.join(img_dir, pic)
        if not os.path.exists(src):
            report["missing_picture"] += 1
            continue
        kept.append({"name": f"arts_{stem}.jpg", "src": src, "lines": lines})
    report["top_unmapped_codes"] = unmapped_counter.most_common(15)
    return kept, report


import random


def cap_photos(items, cap, base_counts=None, class_caps=None, seed=0):
    """Keep whole photos only. A photo is kept if no class in it would go over its cap.
    base_counts = boxes per class we already have (our own footage).
    class_caps = optional {class_number: own cap} to override the default.
    Returns (kept, totals)."""
    class_caps = class_caps or {}
    totals = collections.Counter(base_counts or {})
    freq = collections.Counter()
    for it in items:
        for ln in it["lines"]:
            freq[int(ln.split()[0])] += 1
    order = sorted(items, key=lambda it: it["name"])
    random.Random(seed).shuffle(order)
    order.sort(key=lambda it: min(freq[int(l.split()[0])] for l in it["lines"]))  # rarest first
    kept = []
    for it in order:
        add = collections.Counter(int(l.split()[0]) for l in it["lines"])
        if all(totals[c] + n <= class_caps.get(c, cap) for c, n in add.items()):
            kept.append(it)
            totals.update(add)
    return kept, totals


def make_alias_ids(new_names, rename):
    """{name: class number in the NEW list}. Old names that were merged point at the merged class.
    A dropped name is left out, so using it raises an error instead of being silently lost."""
    ids = {n: i for i, n in enumerate(new_names)}
    alias = dict(ids)
    for old, new in rename.items():
        if new not in ids:
            raise ValueError(f"rename target is not in the new class list: {new}")
        alias[old] = ids[new]
    return alias


import csv

LETTER_TO_NAME = {
    "Y": "Yield Here to Pedestrians",
    "S": "Stop Ahead",
    "R": "Right Lane Must Turn Right",
}


def apply_review(dataset_dir, csv_path, class_ids):
    """Rename other_sign boxes using the review CSV. Edits label files inside dataset_dir.
    Each row is checked first: the line must be other_sign and the box must match the CSV."""
    other_id = class_ids["other_sign"]
    changes = collections.Counter()
    by_file = collections.defaultdict(list)
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            letter = (row["choice"] or "").strip().upper()
            if letter == "":
                continue
            if letter == "D":
                continue                      # dropped for Run F: stays other_sign
            if letter not in LETTER_TO_NAME:
                raise ValueError(f"unknown letter {letter!r} for tile {row['tile']}")
            by_file[(row["split"], row["image"])].append((row, letter))
    for (split, image), rows in by_file.items():
        path = os.path.join(dataset_dir, "labels", split, image + ".txt")
        if not os.path.exists(path):
            raise ValueError(f"label file not found: {path}")
        text = open(path).read()
        lines = text.splitlines()
        for row, letter in rows:
            i = int(row["line_in_label_file"]) - 1          # CSV line numbers start at 1
            if i < 0 or i >= len(lines):
                raise ValueError(f"{image}: line {row['line_in_label_file']} does not exist")
            parts = lines[i].split()
            if len(parts) != 5 or int(parts[0]) != other_id:
                raise ValueError(f"{image} line {row['line_in_label_file']} is not other_sign")
            csv_box = [float(row[k]) for k in ("xc", "yc", "w", "h")]
            if any(abs(float(a) - b) > 1e-5 for a, b in zip(parts[1:], csv_box)):
                raise ValueError(f"{image} line {row['line_in_label_file']}: box does not match the CSV")
            new_name = LETTER_TO_NAME[letter]
            if new_name not in class_ids:
                raise ValueError(f"our class list has no class named: {new_name}")
            lines[i] = f"{class_ids[new_name]} " + " ".join(parts[1:])
            changes[new_name] += 1
        open(path, "w").write("\n".join(lines) + "\n")
    return changes



def read_yaml_names(text):
    """Read '  0: "Name"' lines from a YOLO data.yaml into {number: name}."""
    import json
    names = {}
    for line in text.splitlines():
        s = line.strip()
        if ":" in s and s.split(":", 1)[0].isdigit():
            num, name = s.split(":", 1)
            names[int(num)] = json.loads(name.strip())
    return names


def remap_labels(text, old_names, class_ids):
    """Rewrite each line's class number by NAME. Stops if a name is missing from our list."""
    out = []
    for raw in text.splitlines():
        p = raw.split()
        if not p:
            continue
        if len(p) != 5:
            raise ValueError(f"expected 5 numbers per line, got: {raw!r}")
        idx = int(p[0])
        if idx not in old_names:
            raise ValueError(f"class number {idx} is not in the old list")
        name = old_names[idx]
        if name not in class_ids:
            raise ValueError(f"our class list has no class named: {name}")
        out.append(f"{class_ids[name]} " + " ".join(p[1:]))
    return out


def load_streetview(root, class_ids, split="train"):
    """Read an unzipped Street View dataset. Returns (items, report).
    Class numbers are rewritten by NAME. Items with no boxes are returned too
    (the caller decides what to do with them)."""
    old_names = read_yaml_names(open(os.path.join(root, "data.yaml"), encoding="utf-8").read())
    img_dir = os.path.join(root, "images", split)
    lbl_dir = os.path.join(root, "labels", split)
    pictures = {}
    for f in os.listdir(img_dir):
        stem, ext = os.path.splitext(f)
        if ext.lower() in (".jpg", ".jpeg", ".png"):
            pictures[stem] = f
    items = []
    report = {"labels_seen": 0, "no_picture": 0, "empty": 0}
    for f in sorted(os.listdir(lbl_dir)):
        if not f.endswith(".txt"):
            continue
        report["labels_seen"] += 1
        stem = f[:-4]
        if stem not in pictures:
            report["no_picture"] += 1
            continue
        lines = remap_labels(open(os.path.join(lbl_dir, f)).read(), old_names, class_ids)
        if not lines:
            report["empty"] += 1
        ext = os.path.splitext(pictures[stem])[1]
        items.append({"name": f"sv_{stem}{ext}",
                      "src": os.path.join(img_dir, pictures[stem]),
                      "lines": lines})
    return items, report