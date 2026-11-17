import csv
import os
import sys
from sign_lookup import load_catalog, catalog_index, build_lookup, write_lookup
from review_xlsx import load_class_names

home = os.path.expanduser("~")
catalog_path = sys.argv[1] if len(sys.argv) > 1 else f"{home}/ladot-virtual-drive/LA_Standard_Sign_Catalog.xlsx"
map_rows = list(csv.DictReader(open(f"{home}/ladot-virtual-drive/clips/class_map_v1.csv", newline="")))
names = load_class_names("uncomitted/label_config_G.xml")
entries = build_lookup(map_rows, names, catalog_index(load_catalog(catalog_path)))
out = f"{home}/ladot-virtual-drive/sign_lookup.csv"
write_lookup(entries, out)
filled = sum(1 for e in entries if e["stock_number"])
cands = sum(1 for e in entries if e["candidates"])
print(f"wrote {out}: {len(entries)} classes, {filled} with a stock number, {cands} with candidates")