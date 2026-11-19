import csv
import os
from urllib.parse import urlencode

TIER_ORDER = {"likely": 0, "review": 1}
DECISIONS = ["correct", "wrong name", "not a sign", "can't tell"]
EXTRA_LABELS = []
HIDE_LISTS = True          # set to False if the drop-downs show up empty in Google Sheets
HEADERS = [
    "Picture",
    "Tier",
    "Model's name",
    "Confidence",
    "Decision",
    "Correct name",
    "Map pin",
    "Apple Maps",
    "Times seen",
    "Lat",
    "Lon",
    "Group",
    "Picture file",
    "Catalog match",
    "MUTCD code",
    "Sign close-up",
    "Side of street (suggested)",
    "Sign faces (suggested)",
    "Direction note"
]

WIDTHS = {
    "A": 90,
    "B": 10,
    "C": 30,
    "D": 12,
    "E": 16,
    "F": 30,
    "G": 18,
    "H": 22,
    "I": 12,
    "J": 12,
    "K": 12,
    "L": 8,
    "M": 40,
    "N": 46,
    "O": 14,
    "P": 85, "Q": 22, "R": 22, "S": 28
}

INSTRUCTIONS = [
    "HOW TO REVIEW",
    "",
    "Each row is one sign the model thinks it found. The picture is the best frame, with the box drawn on it.",
    "",
    "Tier: 'likely' = seen in 2 or more frames and the model was at least 40% sure. 'review' = seen once, or less sure.",
    "",
    "Decision (pick from the drop-down):",
    "  correct     - the model found a real sign and named it right",
    "  wrong name  - a real sign, but the name is wrong. Pick the right one in 'Correct name'",
    "  not a sign  - the box is on something that is not a road sign (glare, storefront, etc.)",
    "  can't tell  - you cannot tell from the picture",
    "  (blank)     - not reviewed yet",
    "",
    "Correct name: only fill this in when the decision is 'wrong name'.",
    "",
    "Catalog match: sign number, description and size from the LA Standard Sign Catalog for the model's name. "
    "Several candidates, or 'not in PDF catalog', means GIS picks the final number.",
    "",
    "Map pin: opens Google Maps with a pin at the estimated sign position. The position is an estimate "
        "Sign close-up: the sign cut out of the original frame, so it is easier to see. "
    "Side of street and Sign faces are the model's guess, so please confirm or fix them.",]


def street_view_url(lat, lon):
    """Link to Street View at a point, or None when there is no position."""
    lat, lon = (lat or "").strip(), (lon or "").strip()
    if not lat or not lon:
        return None
    return f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}"

def apple_maps_url(lat, lon, name="LADOT sign"):
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return ""
    return f"https://maps.apple.com/place?coordinate={lat:.6f},{lon:.6f}"

def map_pin_url(lat, lon):
    """Link that drops a pin on Google Maps at a point, or None when there is no position."""
    lat, lon = (lat or "").strip(), (lon or "").strip()
    if not lat or not lon:
        return None
    return f"https://www.google.com/maps/search/?api=1&query={lat}%2C{lon}"

def load_class_names(xml_path):
    """Read the class names from a Label Studio config file, in order."""
    import xml.etree.ElementTree as ET
    root = ET.parse(xml_path).getroot()
    return [lab.get("value")
            for group in root.iter("RectangleLabels")
            for lab in group.findall("Label")]


def sort_rows(rows):
    """Likely first, then review. Inside a tier, strongest first."""
    return sorted(rows, key=lambda r: (TIER_ORDER.get(r["tier"], 2), -float(r["best_conf"])))


def read_review(csv_path):
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


def thumb_size(width, height, max_w=600, max_h=400):
    """Size that fits inside max_w x max_h and keeps the shape. Never enlarges."""
    scale = min(max_w / width, max_h / height, 1.0)
    return max(1, round(width * scale)), max(1, round(height * scale))


def add_dropdowns(wb, ws, n_rows, decisions, labels):
    """Put the option lists on a 'Lists' sheet, then make columns E and F drop-downs."""
    from openpyxl.worksheet.datavalidation import DataValidation

    lists = wb.create_sheet("Lists")
    lists.cell(row=1, column=1, value="decisions")
    lists.cell(row=1, column=2, value="class names")
    for i, v in enumerate(decisions, start=2):
        lists.cell(row=i, column=1, value=v)
    for i, v in enumerate(labels, start=2):
        lists.cell(row=i, column=2, value=v)
    lists.column_dimensions["A"].width = 18
    lists.column_dimensions["B"].width = 40
    if HIDE_LISTS:
        lists.sheet_state = "hidden"
    if n_rows == 0:
        return

    def attach(target_col, src_col, count):
        dv = DataValidation(type="list",
                            formula1=f"Lists!${src_col}$2:${src_col}${count + 1}",   # no leading "="
                            allow_blank=True,
                            showErrorMessage=True,
                            errorStyle="stop",
                            errorTitle="Pick from the list",
                            error="Please choose one of the options in the drop-down.")
        dv.add(f"{target_col}2:{target_col}{n_rows + 1}")
        ws.add_data_validation(dv)

    attach("E", "A", len(decisions))
    attach("F", "B", len(labels))


def add_instructions(wb):
    ws = wb.create_sheet("How to review")
    ws.column_dimensions["A"].width = 110
    for i, line in enumerate(INSTRUCTIONS, start=1):
        c = ws.cell(row=i, column=1, value=line)
        c.alignment = c.alignment.copy(wrap_text=True, vertical="top")
    ws["A1"].font = ws["A1"].font.copy(bold=True, size=14)


def add_catalog_sheet(wb, catalog):
    """Reference copy of the LA Standard Sign Catalog, filterable, so reviewers can look signs up."""
    from openpyxl.styles import Font, PatternFill
    ws = wb.create_sheet("Catalog")
    cols = [("Sign number", "sign_number", 12), ("MUTCD", "mutcd_code", 14), ("SMS number", "sms_number", 16),
            ("Description", "description", 55), ("Size", "size", 14), ("Material", "material", 10),
            ("PDF page", "page", 9), ("Extraction flags", "flags", 40)]
    ws.append([c[0] for c in cols])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3864")
    for letter, (_, _, w) in zip("ABCDEFGH", cols):
        ws.column_dimensions[letter].width = w
    for r in catalog:
        ws.append([r[key] for _, key, _ in cols])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:H{len(catalog) + 1}"

def build_workbook(rows, run_dir, make_thumb, class_names, lookup=None, catalog=None, context=None):
    from sign_lookup import catalog_text
    """make_thumb(path) -> path of a small picture, or None if the picture is missing."""
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "review"
    ws.append(HEADERS)
    for col, w in WIDTHS.items():
        ws.column_dimensions[col].width = w

    ws.column_dimensions["I"].hidden = True
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    head_fill = PatternFill("solid", fgColor="1F3864")
    tier_fill = {"likely": PatternFill("solid", fgColor="C6EFCE"),
                 "review": PatternFill("solid", fgColor="FFEB9C")}

    for c in ws[1]:
        c.fill = head_fill
        c.font = Font(bold=True, color="FFFFFF")
        c.alignment = center
        c.border = border
    ws.row_dimensions[1].height = 28

    missing = 0
    for i, r in enumerate(sort_rows(rows), start=2):
        ws.cell(row=i, column=2, value=r["tier"])
        ws.cell(row=i, column=3, value=r["label"])
        ws.cell(row=i, column=4, value=float(r["best_conf"])).number_format = "0%"
        google_url = map_pin_url(r["lat"], r["lon"])
        ws.cell(
            row=i,
            column=7,
            value=f'=HYPERLINK("{google_url}","Open map pin")'
            if google_url else "needs location"
        )

        apple_url = apple_maps_url(r["lat"], r["lon"], r["label"])
        if apple_url:
            cell = ws.cell(row=i, column=8, value="Open in Apple Maps")
            cell.hyperlink = apple_url
            cell.style = "Hyperlink"
        else:
            ws.cell(row=i, column=8, value="needs location")

        ws.cell(row=i, column=9, value=int(r["n_sightings"]))
        ws.cell(row=i, column=10, value=float(r["lat"]) if r["lat"] else None)
        ws.cell(row=i, column=11, value=float(r["lon"]) if r["lon"] else None)
        ws.cell(row=i, column=12, value=int(r["group_id"]))
        ws.cell(row=i, column=13, value=r["best_picture"])

        entry = (lookup or {}).get(r["label"])
        ws.cell(row=i, column=14, value=catalog_text(entry))
        ws.cell(row=i, column=15, value=(entry or {}).get("mutcd_code", ""))
        thumb = make_thumb(os.path.join(run_dir, r["best_picture"]))
        if thumb:
            ws.add_image(XLImage(thumb), f"A{i}")
        else:
            ws.cell(
                row=i,
                column=1,
                value=f"(picture missing)\nExpected: {r['best_picture']}"
            )
            missing += 1
        ctx = (context or {}).get(r["group_id"], {})
        ws.cell(row=i, column=17, value=ctx.get("side", ""))
        ws.cell(row=i, column=18, value=ctx.get("faces", ""))
        ws.cell(row=i, column=19, value=ctx.get("note", ""))
        if ctx.get("crop"):
            ws.add_image(XLImage(ctx["crop"]), f"P{i}")
        ws.row_dimensions[i].height = 300
        for col in range(1, len(HEADERS) + 1):
            cell = ws.cell(row=i, column=col)
            cell.alignment = center
            cell.border = border
        if r["tier"] in tier_fill:
            ws.cell(row=i, column=2).fill = tier_fill[r["tier"]]

    ws.freeze_panes = "A2"
    add_dropdowns(wb, ws, len(rows), DECISIONS, class_names + EXTRA_LABELS)
    add_instructions(wb)
    if catalog:
           add_catalog_sheet(wb, catalog)
    return wb, missing