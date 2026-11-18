import csv
import re

# Run G name -> name used in class_map_v1.csv
ALIASES = {"Stop Ahead": "STOP AHEAD SYMBOL W3-1",
           "R4-7 Keep Right Arrow": "r4-7(island nose-right)"}

HOLD = {
    "Hourly Parking Signs": "held: class map says 1 stock number, but the singular row has 105 versions"
}

# Selected stock numbers for classes with multiple versions.
# These are assumptions for review, not confirmed matches.
OVERRIDES = {
    "Pedestrian Traffic, (Symbol) 572": (
        "0572", "assumed from class name; 0560, 0561, 0570 also exist"
    ),
    "R3-18_No_U_Turn_or_Left_Turn": (
        "1463", "single catalog row"
    ),
    "No Left Turn": (
        "1397", "plain version assumed; timed versions exist (e.g. 1404)"
    ),
    "No Right Turn": (
        "1381", "plain version assumed"
    ),
}


LOOKUP_FIELDS = ["ladot_name", "stock_number", "mutcd_code", "catalog_description", "status", "candidates", "note"]

def clean(text):
    return re.sub(r"\s+", " ", "" if text is None else str(text)).strip()


def norm_number(text):
    """'316' -> '0316' (catalog numbers are 4 digits); 'P-0276' and '2530da' stay as they are."""
    s = clean(text)
    return s.zfill(4) if s.isdigit() else s


def load_catalog(path):
    """Read the 'Sign Catalog' sheet of the LA Standard Sign Catalog into a list of dicts."""
    from openpyxl import load_workbook
    ws = load_workbook(path, read_only=True, data_only=True)["Sign Catalog"]
    rows = ws.iter_rows(values_only=True)
    head = next(rows)
    out = []
    for r in rows:
        d = dict(zip(head, r))
        if not clean(d.get("Sign Number")):
            continue
        out.append({"sign_number": norm_number(d["Sign Number"]),
                    "mutcd_code": clean(d.get("MUTCD Code", "MUTCD")),
                    "sms_number": clean(d.get("SMS Number", "SMS number")),
                    "description": clean(d.get("Description")),
                    "size": clean(d.get("Size")),
                    "material": clean(d.get("Material")),
                    "page": clean(d.get("Source Page", "PDF page")),
                    "flags": clean(d.get("Review Flags", "Extraction flags"))})
    return out


def catalog_index(catalog):
    index = {}
    for r in catalog:
        index.setdefault(r["sign_number"], []).append(r)
    return index


def describe(number, index):
    rows = index.get(number)
    if not rows:
        return f"{number} (not in PDF catalog)"
    return clean(f"{number} {rows[0]['description']}")

def _count(text):
    try:
        return int(clean(text) or 0)
    except ValueError:
        return -1


def build_lookup(map_rows, class_names, index):
    """One row per class name. A stock number is filled only when the class map row is accepted,
    has exactly 1 stock number, and says the detector can fill it. Classes with a few versions
    list them as candidates. Everything else stays blank with a reason in 'status'."""
    by_name = {clean(r["detector_class"]): r for r in map_rows}
    out = []
    for name in class_names:
        e = {f: "" for f in LOOKUP_FIELDS}
        e["ladot_name"] = name
        row = by_name.get(ALIASES.get(name, name))
        if name in HOLD:
            e["status"], e["note"] = "held", HOLD[name]
        elif row is None:
            e["status"] = "not in class map"
        else:
            review, n = clean(row["review"]), _count(row["n_stock"])
            tokens = [norm_number(t) for t in clean(row["stock_examples"]).split()]
            if review != "accepted":
                e["status"] = f"class map: {review}"
            elif n == 0:
                e["status"] = "no stock number in class map"
            elif n == 1 and len(tokens) == 1 and "fill stock" in clean(row["stage2"]):
                num = tokens[0]
                e["stock_number"], e["mutcd_code"] = num, clean(row["mutcd"])
                hit = index.get(num)
                if hit:
                    e["catalog_description"] = hit[0]["description"]
                    e["mutcd_code"] = e["mutcd_code"] or hit[0]["mutcd_code"]
                    e["status"] = "matched in catalog"
                else:
                    e["status"] = "stock number not in PDF catalog"
            elif n == 1:
                e["status"] = "class map: check before using"
            elif n == len(tokens):
                e["candidates"] = "; ".join(describe(t, index) for t in tokens)
                e["status"] = f"{n} candidates"
            else:
                e["status"] = f"{n} versions (too many to list)"
        if name in OVERRIDES:
            raw_number, note = OVERRIDES[name]
            number = norm_number(raw_number)
            hit = index.get(number)

            e["stock_number"] = number
            e["mutcd_code"] = hit[0]["mutcd_code"] if hit else ""
            e["catalog_description"] = hit[0]["description"] if hit else ""
            e["candidates"] = ""
            e["status"] = "assumed - review"
            e["note"] = note
        
        out.append(e)
    return out


def write_lookup(entries, path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOOKUP_FIELDS)
        w.writeheader()
        w.writerows(entries)


def read_lookup(path):
    """Lookup file -> {class name: row}."""
    with open(path, newline="") as f:
        return {r["ladot_name"]: r for r in csv.DictReader(f)}


def catalog_text(entry):
    """Short text for the 'Catalog match' column of the review sheet."""
    if not entry:
        return ""
    if entry.get("stock_number"):
        text = clean(
            f"{entry['stock_number']} {entry.get('catalog_description', '')}"
        )
        if entry.get("status") == "matched in catalog":
            return text

        if entry.get("status") == "assumed - review":
            return f"{text} (assumed - review)"
        return f"{text} (not in PDF catalog)"
    
    return entry.get("candidates") or entry.get("status", "")