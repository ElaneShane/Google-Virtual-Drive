import os
import sys
import tempfile
from PIL import Image
from review_xlsx import read_review, build_workbook, thumb_size, load_class_names

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
wb, missing = build_workbook(rows, run_dir, make_thumb, class_names)
out_path = os.path.join(run_dir, "review.xlsx")
wb.save(out_path)
print(f"wrote {out_path}: {len(rows)} rows, {missing} missing pictures")
print(f"size: {os.path.getsize(out_path) / 1024:.0f} KB")