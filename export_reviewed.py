import csv
import os
import sys

EXPORT_FIELDS = ["sign_name", "lat", "lon", "stock_number", "mutcd_code", "catalog_description",
                    "catalog_status", "candidates", "confidence", "tier", "times_seen", "group_id", "name_changed", "source_run"]
NOT_EXPORTED_FIELDS = EXPORT_FIELDS + ["reason"]


def _s(v):
    return "" if v is None else str(v).strip()


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def _whole(v):
    """2.0 -> 2. Google Sheets downloads store whole numbers as floats."""
    return int(v) if isinstance(v, float) and v.is_integer() else v

def read_reviewed(path):
    """Read the 'review' sheet by header names, so moving a column does not break this."""
    from openpyxl import load_workbook
    ws = load_workbook(path, data_only=True)["review"]
    rows = ws.iter_rows(values_only=True)
    head = [_s(h) for h in next(rows)]
    return [d for d in (dict(zip(head, r)) for r in rows) if _s(d.get("Model's name"))]


def split_for_export(rows, lookup, source_run):
    """Return (export_rows, not_exported_rows). A row is exported only when it is marked
    correct / wrong name, has a final name, and has a position."""
    good, held = [], []
    for r in rows:
        decision = _s(r.get("Decision")).lower()
        name = _s(r.get("Model's name"))
        if decision == "wrong name":
            name = _s(r.get("Correct name"))
        lat, lon = _num(r.get("Lat")), _num(r.get("Lon"))
        if decision == "":
            reason = "not reviewed"
        elif decision in ("not a sign", "can't tell"):
            reason = decision
        elif decision not in ("correct", "wrong name"):
            reason = f"unknown decision: {decision}"
        elif not name:
            reason = "wrong name but no correct name given"
        elif lat is None or lon is None:
            reason = "needs location"
        else:
            reason = ""
        e = lookup.get(name, {})
        out = {"sign_name": name, "lat": "" if lat is None else lat, "lon": "" if lon is None else lon,
               "stock_number": e.get("stock_number", ""), 
               "mutcd_code": e.get("mutcd_code", ""),
               "catalog_description": e.get("catalog_description", ""),
               
               "catalog_status": e.get("status", "name not in lookup" if name else ""),
               "candidates": e.get("candidates", ""),
               "confidence": r.get("Confidence", ""), "tier": _s(r.get("Tier")),
              "times_seen": _whole(r.get("Times seen", "")), "group_id": _whole(r.get("Group", "")),
               "name_changed": "yes" if decision == "wrong name" else "",
               "source_run": source_run}
        if reason:
            out["reason"] = reason
            held.append(out)
        else:
            good.append(out)
    return good, held


def write_csv(rows, fields, path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    from sign_lookup import read_lookup
    run_dir = os.path.expanduser(sys.argv[1])
    lookup_path = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else "~/ladot-virtual-drive/sign_lookup.csv")
    rows = read_reviewed(os.path.join(run_dir, "review.xlsx"))
    good, held = split_for_export(rows, read_lookup(lookup_path), os.path.basename(os.path.normpath(run_dir)))
    write_csv(good, EXPORT_FIELDS, os.path.join(run_dir, "gis_export.csv"))
    write_csv(held, NOT_EXPORTED_FIELDS, os.path.join(run_dir, "not_exported.csv"))
    print(f"{len(rows)} rows: {len(good)} exported, {len(held)} not exported")
    for reason in sorted({h["reason"] for h in held}):
        print(f"  {reason}: {sum(1 for h in held if h['reason'] == reason)}")