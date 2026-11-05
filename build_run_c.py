import argparse
import collections
import csv
import hashlib
import json
import os
import shutil
import sys

from ls_to_yolo import load_class_names, parse_task, resolve_image


def sha1_of(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(exports, class_ids, media_root, local_root):
    items, problems = [], []
    for spec in exports:
        tag, path = spec.split("=", 1)
        with open(os.path.expanduser(path)) as f:
            tasks = json.load(f)
        for t in tasks:
            img = t["data"]["image"]
            try:
                src = resolve_image(img, media_root, local_root)
                lines, cond, probs = parse_task(t, class_ids)
            except ValueError as e:
                problems.append(f"[{tag}] {img}: {e}")
                continue
            problems += [f"[{tag}] {img}: {p}" for p in probs]
            if not os.path.exists(src):
                problems.append(f"[{tag}] missing image file: {src}")
                continue
            base = os.path.basename(src)
            items.append({"tag": tag, "src": src, "base": base,
                          "name": f"{tag}_{base}", "lines": lines,
                          "condition": cond, "split": "train"})
    return items, problems


def main():
    p = argparse.ArgumentParser(description="Label Studio exports -> YOLO dataset (audit or build)")
    p.add_argument("--config", required=True, help="Label Studio XML config (class order)")
    p.add_argument("--export", action="append", required=True, help="TAG=/full/path/export.json (repeatable)")
    p.add_argument("--media-root", default=os.path.expanduser("~/.local/share/label-studio/media"))
    p.add_argument("--local-root", default="~/Google-Virtual-Drive/data/youtube_sources")
    p.add_argument("--val-list", help="text file: one Label Studio image filename per line = validation")
    p.add_argument("--out", help="new folder to write the dataset into (must not exist)")
    p.add_argument("--yaml-path", default="/content/run_c", help="where the dataset will live on Colab")
    args = p.parse_args()

    names = load_class_names(os.path.expanduser(args.config))
    class_ids = {n: i for i, n in enumerate(names)}
    print("classes in config:", len(names))

    items, problems = collect(args.export, class_ids, args.media_root, os.path.expanduser(args.local_root))

    names_seen = collections.Counter(it["name"] for it in items)
    problems += [f"duplicate output name: {n}" for n, c in names_seen.items() if c > 1]

    by_hash = collections.defaultdict(list)
    for it in items:
        by_hash[sha1_of(it["src"])].append(it["name"])
    dups = [v for v in by_hash.values() if len(v) > 1]
    if dups:
        print(f"WARNING: {len(dups)} groups of identical image files (same picture twice):")
        for g in dups[:10]:
            print("  ", g)

    if args.val_list:
        wanted = {ln.strip() for ln in open(args.val_list) if ln.strip() and not ln.startswith("#")}
        have = {it["base"] for it in items}
        for w in sorted(wanted - have):
            problems.append(f"val-list name not found in exports: {w}")
        for it in items:
            if it["base"] in wanted:
                it["split"] = "val"

    if problems:
        print(f"\nSTOPPING: {len(problems)} problem(s):")
        for pr in problems:
            print("  -", pr)
        sys.exit(1)

    print("\nimages per source:", dict(collections.Counter(it["tag"] for it in items)))
    print("frames with no boxes:", sum(1 for it in items if not it["lines"]))
    print("split:", dict(collections.Counter(it["split"] for it in items)))
    per_class = collections.Counter()
    per_class_val = collections.Counter()
    for it in items:
        for ln in it["lines"]:
            cid = int(ln.split()[0])
            per_class[cid] += 1
            if it["split"] == "val":
                per_class_val[cid] += 1
    print("\nboxes per class (total, of which in val):")
    for i, n in enumerate(names):
        print(f"  {i:>2} {n}: {per_class[i]} ({per_class_val[i]})")
    print("classes with zero boxes:", sum(1 for i in range(len(names)) if per_class[i] == 0))

    if not (args.val_list and args.out):
        print("\nAUDIT ONLY: nothing written (needs --val-list and --out to build).")
        return

    out = os.path.expanduser(args.out)
    if os.path.exists(out):
        sys.exit(f"Output folder already exists, refusing to mix: {out}")
    for sp in ("train", "val"):
        os.makedirs(f"{out}/images/{sp}")
        os.makedirs(f"{out}/labels/{sp}")
    for it in items:
        sp = it["split"]
        shutil.copy2(it["src"], f"{out}/images/{sp}/{it['name']}")
        stem = os.path.splitext(it["name"])[0]
        with open(f"{out}/labels/{sp}/{stem}.txt", "w") as f:
            f.write("\n".join(it["lines"]) + ("\n" if it["lines"] else ""))
    with open(f"{out}/data.yaml", "w") as f:
        f.write(f"path: {args.yaml_path}\ntrain: images/train\nval: images/val\nnames:\n")
        for i, n in enumerate(names):
            f.write(f"  {i}: {json.dumps(n)}\n")
    with open(f"{out}/manifest.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "source", "split", "boxes", "condition"])
        for it in items:
            w.writerow([it["name"], it["tag"], it["split"], len(it["lines"]), it["condition"]])
    print(f"\nBUILT {len(items)} images into {out}")


if __name__ == "__main__":
    main()