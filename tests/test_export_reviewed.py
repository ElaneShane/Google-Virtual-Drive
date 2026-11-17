from export_reviewed import read_reviewed, split_for_export
from review_xlsx import build_workbook

LOOKUP = {"Stop Ahead": {"stock_number": "0161", "sms_number": "55", "mutcd_code": "W3-1",
                         "catalog_description": "Stop Ahead", "catalog_size": "36x36",
                         "status": "matched in catalog", "candidates": ""},
          "Stop Signs 1022": {"stock_number": "", "candidates": "1010 ...; 1022 ...", "status": "2 candidates"}}


def fake(i, label="Stop Ahead", lat="34.1", lon="-118.2"):
    return {"group_id": str(i), "tier": "likely", "label": label, "n_sightings": "2",
            "best_conf": "0.8", "lat": lat, "lon": lon, "best_picture": "x.jpg"}


def reviewed(tmp_path, rows, decisions):
    wb, _ = build_workbook(rows, ".", lambda p: None, ["Stop Ahead"], LOOKUP)
    ws = wb["review"]
    for i, (dec, name) in enumerate(decisions, start=2):
        ws.cell(row=i, column=5, value=dec)
        ws.cell(row=i, column=6, value=name)
    p = tmp_path / "review.xlsx"
    wb.save(str(p))
    return read_reviewed(str(p))


def test_correct_row_exports_with_catalog_fields(tmp_path):
    rows = reviewed(tmp_path, [fake(1)], [("correct", None)])
    good, held = split_for_export(rows, LOOKUP, "run1")
    assert held == [] and good[0]["stock_number"] == "0161"
    assert good[0]["mutcd_code"] == "W3-1" and good[0]["catalog_description"] == "Stop Ahead"
    assert good[0]["source_run"] == "run1"

def test_wrong_name_uses_corrected_name_for_lookup(tmp_path):
    rows = reviewed(tmp_path, [fake(1, "Stop Signs 1022")], [("wrong name", "Stop Ahead")])
    good, _ = split_for_export(rows, LOOKUP, "r")
    assert good[0]["sign_name"] == "Stop Ahead" and good[0]["stock_number"] == "0161"
    assert good[0]["name_changed"] == "yes"


def test_rows_that_must_not_export_get_a_reason(tmp_path):
    rs = [fake(1), fake(2), fake(3), fake(4, lat="", lon=""), fake(5)]
    dec = [("not a sign", None), ("can't tell", None), (None, None), ("correct", None), ("wrong name", None)]
    good, held = split_for_export(reviewed(tmp_path, rs, dec), LOOKUP, "r")
    assert good == []
    assert sorted(h["reason"] for h in held) == sorted(
        ["not a sign", "can't tell", "not reviewed", "needs location", "wrong name but no correct name given"])


def test_candidates_pass_through_when_no_single_stock_number(tmp_path):
    rows = reviewed(tmp_path, [fake(1, "Stop Signs 1022")], [("correct", None)])
    good, _ = split_for_export(rows, LOOKUP, "r")
    assert good[0]["stock_number"] == "" and good[0]["candidates"].startswith("1010")

def test_whole_numbers_from_sheets_downloads_lose_the_dot_zero():
    row = {"Model's name": "Stop Ahead", "Decision": "correct", "Lat": 34.1, "Lon": -118.2,
           "Group": 16.0, "Times seen": 2.0}
    good, _ = split_for_export([row], LOOKUP, "r")
    assert good[0]["group_id"] == 16 and good[0]["times_seen"] == 2