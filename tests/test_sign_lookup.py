
from sign_lookup import (
    build_lookup,
    catalog_index,
    catalog_text,
    norm_number,
    read_lookup,
    write_lookup,
)


CATALOG = [
    {
        "sign_number": "0161",
        "mutcd_code": "W3-1",
        "description": "Stop Ahead",
    },
    {
        "sign_number": "1010",
        "mutcd_code": "R1-1",
        "description": "STOP (Signal Repair)",
    },
    {
        "sign_number": "1022",
        "mutcd_code": "R1-1",
        "description": "Stop, High Intensity",
    },
]

INDEX = catalog_index(CATALOG)


def row(
    name,
    status="confirmed",
    stock="0161",
    mutcd="W3-1",
    **extra,
):
    result = {
        "detector_class": name,
        "mapping_status": status,
        "stock_examples": stock,
        "mutcd": mutcd,
        "note": "",
        "review_instructions": "",
        "catalog_description": "",
        "catalog_candidates": "",
    }
    result.update(extra)
    return result


def test_norm_number_pads_digits_only():
    assert norm_number("316") == "0316"
    assert norm_number("P-0276") == "P-0276"
    assert norm_number(" 2530da ") == "2530da"


def test_confirmed_single_match_fills_from_catalog():
    entry = build_lookup(
        [row("STOP AHEAD SYMBOL W3-1")],
        ["Stop Ahead"],
        INDEX,
    )[0]

    assert entry["stock_number"] == "0161"
    assert entry["mutcd_code"] == "W3-1"
    assert entry["catalog_description"] == "Stop Ahead"
    assert entry["status"] == "matched in master catalog"


def test_confirmed_stock_missing_from_catalog_still_fills():
    entry = build_lookup(
        [
            row(
                "Street Name Sign 4215",
                stock="4215",
                mutcd="",
                catalog_description="Street Name Sign",
            )
        ],
        ["Street Name Sign 4215"],
        INDEX,
    )[0]

    assert entry["stock_number"] == "4215"
    assert entry["status"] == "stock number not in master catalog"
    assert catalog_text(entry) == "4215 Street Name Sign"


def test_assumed_match_fills_stock_but_marks_for_review():
    entry = build_lookup(
        [row("No Right Turn", status="assumed_review", stock="1381")],
        ["No Right Turn"],
        INDEX,
    )[0]

    assert entry["stock_number"] == "1381"
    # assert entry["status"] == "assumed - review"
    assert "best guess, please confirm" in catalog_text(entry)


def test_multiple_options_leave_stock_blank():
    entry = build_lookup(
        [
            row(
                "Stop Signs 1022",
                status="options_for_frame_review",
                stock="1010 | 1022",
                mutcd="R1-1",
            )
        ],
        ["Stop Signs 1022"],
        INDEX,
    )[0]

    assert entry["stock_number"] == ""
    assert "1010 STOP (Signal Repair)" in entry["candidates"]
    assert "1022 Stop, High Intensity" in entry["candidates"]
    assert entry["status"] == "options - review frame"


def test_schedule_dependent_mapping_leaves_stock_blank():
    entry = build_lookup(
        [
            row(
                "Hourly Parking Signs",
                status="schedule_review_no_stock",
                stock="P-0276",
                mutcd="",
            )
        ],
        ["Hourly Parking Signs"],
        INDEX,
    )[0]

    assert entry["stock_number"] == ""
    assert entry["status"] == "schedule_review_no_stock"


def test_frame_text_review_leaves_stock_blank():
    entry = build_lookup(
        [
            row(
                "Speed Limit",
                status="frame_text_review_no_stock",
                stock="",
                mutcd="R2-1",
            )
        ],
        ["Speed Limit"],
        INDEX,
    )[0]

    assert entry["stock_number"] == ""
    assert entry["mutcd_code"] == "R2-1"
    assert entry["status"] == "frame_text_review_no_stock"


def test_unresolved_mapping_shows_candidates_without_selecting():
    entry = build_lookup(
        [
            row(
                "One Way with Arrow",
                status="unresolved",
                stock="",
                catalog_candidates="1265 One Way || 1270 One Way",
            )
        ],
        ["One Way with Arrow"],
        INDEX,
    )[0]

    assert entry["stock_number"] == ""
    assert entry["status"] == "unresolved - human review"
    assert entry["candidates"] == (
        "1265 (not in master catalog); "
        "1270 (not in master catalog)"
    )

def test_class_not_in_map_stays_unmatched():
    entry = build_lookup(
        [],
        ["School"],
        INDEX,
    )[0]

    assert entry["stock_number"] == ""
    assert entry["status"] == "not in class map"


def test_aliases_are_applied():
    entry = build_lookup(
        [
            row(
                "Must Turn Right (Text)",
                status="options_for_frame_review",
                stock="1410 | 1420",
            )
        ],
        ["Right Lane Must Turn Right"],
        INDEX,
    )[0]

    assert entry["ladot_name"] == "Right Lane Must Turn Right"
    assert entry["stock_number"] == ""
    assert entry["status"] == "options - review frame"


def test_confirmed_mapping_requires_exactly_one_stock_number():
    entry = build_lookup(
        [
            row(
                "Bad Mapping",
                status="confirmed",
                stock="1010 | 1022",
            )
        ],
        ["Bad Mapping"],
        INDEX,
    )[0]

    assert entry["stock_number"] == ""
    assert entry["status"] == "class map warning: expected one stock number"


def test_lookup_file_round_trip(tmp_path):
    entries = build_lookup(
        [row("STOP AHEAD SYMBOL W3-1")],
        ["Stop Ahead"],
        INDEX,
    )

    path = tmp_path / "lookup.csv"
    write_lookup(entries, str(path))

    loaded = read_lookup(str(path))

    assert loaded["Stop Ahead"]["stock_number"] == "0161"
    assert loaded["Stop Ahead"]["status"] == "matched in master catalog"

def test_catalog_text_options_say_pick_one():
    entry = {"stock_number": "", "status": "options - review frame",
             "candidates": "1010 STOP (Signal Repair); 1022 Stop, High Intensity"}
    assert catalog_text(entry).startswith("Pick one: 1010")


def test_catalog_text_schedule_says_type_it_yourself():
    entry = {"stock_number": "", "status": "schedule_review_no_stock", "candidates": ""}
    assert "Type the stock number yourself" in catalog_text(entry)


def test_catalog_text_no_match_says_so():
    entry = {"stock_number": "", "status": "not in class map", "candidates": ""}
    assert catalog_text(entry).startswith("No stock number found")