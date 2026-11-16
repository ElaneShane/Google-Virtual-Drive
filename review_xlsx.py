import csv
import os

TIER_ORDER = {"likely": 0, "review": 1}
COLUMNS = ["group_id", "tier", "label", "n_sightings", "best_conf", "lat", "lon",
           "picture", "reviewer_decision", "reviewer_label", "best_picture"]

DECISIONS = ["correct", "wrong name", "not a sign", "can't tell"]
EXTRA_LABELS = []          # for example ["not a road sign"] if you want it back
OPTION_COLS = {"decision": 13, "label": 14}   # columns M and N hold the drop-down lists


def load_class_names(xml_path):
    """Read the class names from a Label Studio config file, in order."""
    import xml.etree.ElementTree as ET
    root = ET.parse(xml_path).getroot()
    return [lab.get("value")
            for group in root.iter("RectangleLabels")
            for lab in group.findall("Label")]


def add_dropdowns(ws, n_rows, decisions, labels):
    """Write the option lists into columns M and N, then make columns I and J
    drop-downs that only accept those options."""
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    ws.cell(row=1, column=OPTION_COLS["decision"], value="decision_options")
    ws.cell(row=1, column=OPTION_COLS["label"], value="label_options")
    for i, v in enumerate(decisions, start=2):
        ws.cell(row=i, column=OPTION_COLS["decision"], value=v)
    for i, v in enumerate(labels, start=2):
        ws.cell(row=i, column=OPTION_COLS["label"], value=v)
    for key in OPTION_COLS:
        ws.column_dimensions[get_column_letter(OPTION_COLS[key])].width = 34
    if n_rows == 0:                      # no data rows, so nothing to attach a rule to
        return

    def attach(target_col, option_key, count):
        src = get_column_letter(OPTION_COLS[option_key])
        dv = DataValidation(type="list",
                            formula1=f"${src}$2:${src}${count + 1}",   # no leading "="
                            allow_blank=True,
                            showErrorMessage=True,
                            errorStyle="stop",
                            errorTitle="Pick from the list",
                            error="Please choose one of the options in the drop-down.")
        dv.add(f"{target_col}2:{target_col}{n_rows + 1}")
        ws.add_data_validation(dv)

    attach("I", "decision", len(decisions))
    attach("J", "label", len(labels))

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


def build_workbook(rows, run_dir, make_thumb, class_names):
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
    add_dropdowns(ws, len(rows), DECISIONS, class_names + EXTRA_LABELS)
    return wb, missing