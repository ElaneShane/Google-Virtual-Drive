import os
import sys
import tempfile
from PIL import Image
from review_xlsx import read_review, build_workbook, thumb_size, load_class_names
from sign_lookup import read_lookup
from sign_context import sign_context_for_row
from master_catalog import load_master_catalog

run_dir = os.path.expanduser(sys.argv[1])
tmp = tempfile.mkdtemp()


def make_thumb(path):
    if not os.path.exists(path):
        return None
    im = Image.open(path)
    im = im.convert("RGB").resize(thumb_size(*im.size), Image.LANCZOS)
    out = os.path.join(tmp, f"t{abs(hash(path))}.jpg")
    im.save(out, quality=80)
    return out


rows = read_review(os.path.join(run_dir, "review.csv"))
class_names = load_class_names("uncomitted/label_config_G.xml")

home = os.path.expanduser("~")
catalog_path = f"{home}/ladot-virtual-drive/Elane-Merged Master Sign Catalog - Revised 2025.10.29.xlsx"
catalog = load_master_catalog(catalog_path) if os.path.exists(catalog_path) else None
context = {r["group_id"]: sign_context_for_row(run_dir, r, tmp) for r in rows}

lookup_path = f"{home}/ladot-virtual-drive/sign_lookup.csv"
lookup = read_lookup(lookup_path) if os.path.exists(lookup_path) else None
wb, missing = build_workbook(rows, run_dir, make_thumb, class_names, lookup, catalog, context)
out_path = os.path.join(run_dir, "review.xlsx")
wb.save(out_path)
print(f"wrote {out_path}: {len(rows)} rows, {missing} missing pictures")
print(f"size: {os.path.getsize(out_path) / 1024:.0f} KB")