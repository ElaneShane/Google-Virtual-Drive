import csv
import os

TIER_ORDER = {"likely": 0, "review": 1}
COLUMNS = ["group_id", "tier", "label", "n_sightings", "best_conf", "lat", "lon",
           "picture", "reviewer_decision", "reviewer_label", "best_picture"]


def sort_rows(rows):
    """Likely first, then review. Inside a tier, strongest first."""
    return sorted(rows, key=lambda r: (TIER_ORDER.get(r["tier"], 2), -float(r["best_conf"])))


def read_review(csv_path):
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


def thumb_size(width, height, max_w=420, max_h=240):
    """Size that fits inside max_w x max_h and keeps the shape. Never enlarges."""
    scale = min(max_w / width, max_h / height, 1.0)
    return max(1, round(width * scale)), max(1, round(height * scale))


def build_workbook(rows, run_dir, make_thumb):
    """make_thumb(path) -> path of a small picture, or None if the picture is missing."""
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage

    wb = Workbook()
    ws = wb.active
    ws.title = "review"
    ws.append(COLUMNS)
    widths = {"A": 9, "B": 9, "C": 32, "D": 11, "E": 10, "F": 12, "G": 12,
              "H": 62, "I": 18, "J": 22, "K": 50}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    missing = 0
    for i, r in enumerate(sort_rows(rows), start=2):
        ws.cell(row=i, column=1, value=int(r["group_id"]))
        ws.cell(row=i, column=2, value=r["tier"])
        ws.cell(row=i, column=3, value=r["label"])
        ws.cell(row=i, column=4, value=int(r["n_sightings"]))
        ws.cell(row=i, column=5, value=float(r["best_conf"]))
        ws.cell(row=i, column=6, value=float(r["lat"]) if r["lat"] else None)
        ws.cell(row=i, column=7, value=float(r["lon"]) if r["lon"] else None)
        ws.cell(row=i, column=11, value=r["best_picture"])
        thumb = make_thumb(os.path.join(run_dir, r["best_picture"]))
        if thumb:
            ws.add_image(XLImage(thumb), f"H{i}")
        else:
            ws.cell(row=i, column=8, value="(picture missing)")
            missing += 1
        ws.row_dimensions[i].height = 190
    ws.freeze_panes = "A2"
    return wb, missing