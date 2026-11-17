from sign_lookup import (build_lookup, catalog_index, catalog_text, norm_number,
                         read_lookup, write_lookup)

CATALOG = [
    {"sign_number": "0161", "mutcd_code": "W3-1", "sms_number": "551215030906",
     "description": "Stop Ahead", "size": "36x36"},
    {"sign_number": "1010", "mutcd_code": "R1-1", "sms_number": "1", "description": "STOP (Signal Repair)", "size": '24"Dia.'},
    {"sign_number": "1022", "mutcd_code": "R1-1", "sms_number": "2", "description": "Stop, High Intensity", "size": '30"DIA'},
]
INDEX = catalog_index(CATALOG)


def row(name, review="accepted", n="1", stock="0161", mutcd="W3-1", stage2="detector can fill stock"):
    return {"detector_class": name, "review": review, "n_stock": n,
            "stock_examples": stock, "mutcd": mutcd, "stage2": stage2}


def test_norm_number_pads_digits_only():
    assert norm_number("316") == "0316"
    assert norm_number("P-0276") == "P-0276"
    assert norm_number(" 2530da ") == "2530da"


def test_single_match_fills_from_catalog():
    e = build_lookup([row("STOP AHEAD SYMBOL W3-1")], ["Stop Ahead"], INDEX)[0]
    assert (e["stock_number"], e["mutcd_code"], e["catalog_description"], e["status"]) == (
           "0161", "W3-1", "Stop Ahead", "matched in catalog")

def test_single_stock_missing_from_catalog_still_fills_but_says_so():
    e = build_lookup([row("Street Name Sign 4215", stock="4215", mutcd="")],
                     ["Street Name Sign 4215"], INDEX)[0]
    assert e["stock_number"] == "4215" and e["status"] == "stock number not in PDF catalog"
    assert catalog_text(e) == "4215 (not in PDF catalog)"


def test_few_versions_list_candidates_and_leave_stock_blank():
    e = build_lookup([row("Stop Signs 1022", n="2", stock="1010 1022", mutcd="R1-1")],
                     ["Stop Signs 1022"], INDEX)[0]
    assert e["stock_number"] == ""
    assert "1010 STOP (Signal Repair)" in e["candidates"] and "1022 Stop, High Intensity" in e["candidates"]


def test_many_versions_missing_unreviewed_and_held_stay_blank():
    rows = [row("A", n="105", stock="1 2 3 4"), row("B", review="needs human", n="0", stock=""),
            row("Hourly Parking Signs", stock="P-0276")]
    out = build_lookup(rows, ["A", "B", "C", "Hourly Parking Signs"], INDEX)
    assert [o["stock_number"] for o in out] == ["", "", "", ""]
    assert out[0]["status"].startswith("105 versions")
    assert out[2]["status"] == "not in class map"
    assert out[3]["status"] == "held"


def test_lookup_file_round_trip(tmp_path):
    entries = build_lookup([row("STOP AHEAD SYMBOL W3-1")], ["Stop Ahead"], INDEX)
    p = tmp_path / "l.csv"
    write_lookup(entries, str(p))
    assert read_lookup(str(p))["Stop Ahead"]["stock_number"] == "0161"