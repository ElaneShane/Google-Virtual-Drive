import csv
from helper import addToGISFormatTable, GIS_FIELDS


def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def test_header_matches_layer_fields(tmp_path):
    out = tmp_path / "signs.csv"
    addToGISFormatTable(str(out), "Stop Signs 1022", 34.19, -118.29, 90.0)
    with open(out, newline="") as f:
        header = next(csv.reader(f))
    assert header == GIS_FIELDS


def test_located_sign_fills_only_known_columns(tmp_path):
    out = tmp_path / "signs.csv"
    addToGISFormatTable(str(out), "Stop Signs 1022", 34.19, -118.29, 90.0)
    row = read_rows(out)[0]
    assert row["x"] == "-118.29"
    assert row["y"] == "34.19"
    assert row["Sign_Type"] == "Stop Signs 1022"
    assert row["Stock_Number"] == ""          # blank, not "n/a"
    assert "n/a" not in row.values()


def test_unlocated_sign_has_blank_x_and_y(tmp_path):
    out = tmp_path / "signs.csv"
    addToGISFormatTable(str(out), "Yellow Arrow", None, None, None)
    row = read_rows(out)[0]
    assert row["x"] == "" and row["y"] == ""
    assert row["Sign_Type"] == "Yellow Arrow"


def test_second_call_appends_without_second_header(tmp_path):
    out = tmp_path / "signs.csv"
    addToGISFormatTable(str(out), "A", 1.0, 2.0, 0)
    addToGISFormatTable(str(out), "B", 3.0, 4.0, 0)
    assert len(read_rows(out)) == 2