
import csv
import os
import sys

from review_xlsx import load_class_names
from master_catalog import load_master_catalog
from sign_lookup import catalog_index, build_lookup, write_lookup

home = os.path.expanduser("~")
project_dir = os.path.join(home, "ladot-virtual-drive")
config_dir = os.path.join(project_dir, "clips")

map_path = os.path.join(
    config_dir, "class_map_v3_proposed.csv"
)

catalog_path = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.path.join(
        project_dir,
        "Elane-Merged Master Sign Catalog - Revised 2025.10.29.xlsx"
    )
)

label_config_path = os.path.join(
    home, "Google-Virtual-Drive",
    "uncomitted", "label_config_G.xml"
)

out_path = os.path.join(
    project_dir, "sign_lookup.csv"
)

with open(map_path, newline="", encoding="utf-8-sig") as f:
    map_rows = list(csv.DictReader(f))

names = load_class_names(label_config_path)
catalog = load_master_catalog(catalog_path)

entries = build_lookup(
    map_rows,
    names,
    catalog_index(catalog)
)

write_lookup(entries, out_path)

filled = sum(1 for e in entries if e["stock_number"])
candidates = sum(1 for e in entries if e["candidates"])
assumed = sum(
    1 for e in entries
    if e["status"] == "assumed - review"
)

print(
    f"wrote {out_path}: "
    f"{len(entries)} classes, "
    f"{filled} with a stock number, "
    f"{candidates} with candidates, "
    f"{assumed} assumed for review"
)
