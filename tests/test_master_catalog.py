
from openpyxl import Workbook

from master_catalog import load_master_catalog


def _book(tmp_path):
    wb = Workbook()
    main = wb.active
    main.title = "Main Sign List"
    main.append([
        "TABLE_ID", "TYPE_OF_SIGNS", "MUTCD_CODE",
        "STOCK_NUMBER", "DESCRIPTION", "ALT_DESC"
    ])
    main.append([
        903, "STREET NAME", None, "4215",
        "Street Name Sign High Level", None
    ])
    main.append([
        5, "WARNING", "W1-4L", 11,
        "Reverse Curve Left", None
    ])
    main.append([
        6, "WARNING", "W3-1", "0161smm",
        "Stop Ahead", None
    ])
    main.append([
        7, "WARNING", "W1", None,
        "No stock number", None
    ])

    # These sheets must deliberately be ignored.
    parking = wb.create_sheet("9999 - Parking signs")
    parking.append(["Stock Number", "Name"])
    parking.append(["P-0276", "Parking Sign"])

    street = wb.create_sheet("9999 - Street and neighborhood")
    street.append(["Stock Number", "Name"])
    street.append(["S-0001", "Ceremonial Sign"])

    path = tmp_path / "catalog.xlsx"
    wb.save(path)
    return str(path)


def test_reads_main_list_and_cleans_numbers(tmp_path):
    rows = load_master_catalog(_book(tmp_path))
    by_num = {r["sign_number"]: r for r in rows}

    assert len(rows) == 3
    assert by_num["4215"]["description"] == "Street Name Sign High Level"
    assert by_num["0011"]["mutcd_code"] == "W1-4L"
    assert "0161smm" in by_num
    assert "" not in by_num


def test_ignores_other_worksheets(tmp_path):
    rows = load_master_catalog(_book(tmp_path))
    numbers = {r["sign_number"] for r in rows}

    assert "P-0276" not in numbers
    assert "S-0001" not in numbers


def test_has_expected_output_fields(tmp_path):
    expected = {
        "sign_number", "mutcd_code", "sms_number", "description",
        "size", "material", "page", "flags"
    }

    for row in load_master_catalog(_book(tmp_path)):
        assert set(row) == expected


def test_missing_optional_columns_and_tabs_are_fine(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Main Sign List"
    ws.append(["STOCK_NUMBER", "DESCRIPTION"])
    ws.append(["1397", "NO LEFT TURN"])

    path = tmp_path / "small.xlsx"
    wb.save(path)

    rows = load_master_catalog(str(path))

    assert len(rows) == 1
    assert rows[0]["sign_number"] == "1397"
    assert rows[0]["description"] == "NO LEFT TURN"
    assert rows[0]["mutcd_code"] == ""


def test_missing_main_sign_list_raises_error(tmp_path):
    wb = Workbook()
    wb.active.title = "Other Sheet"

    path = tmp_path / "missing.xlsx"
    wb.save(path)

    import pytest

    with pytest.raises(ValueError, match="Main Sign List"):
        load_master_catalog(str(path))
