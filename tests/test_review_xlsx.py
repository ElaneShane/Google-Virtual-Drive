from review_xlsx import (
    sort_rows, thumb_size, build_workbook, load_class_names,
    DECISIONS, map_pin_url, apple_maps_url
)


def fake_row(i, lat="", lon=""):
    return {"group_id": str(i), "tier": "likely", "label": "Stop Signs 1022",
            "n_sightings": "2", "best_conf": "0.8", "lat": lat, "lon": lon,
            "best_picture": "x.jpg"}


def make_wb(n_rows, names, lat="", lon=""):
    rows = [fake_row(i, lat, lon) for i in range(n_rows)]
    wb, _ = build_workbook(rows, ".", lambda p: None, names)
    return wb


def test_likely_comes_before_review_then_by_confidence():
    rows = [
        {"tier": "review", "best_conf": "0.9"},
        {"tier": "likely", "best_conf": "0.5"},
        {"tier": "likely", "best_conf": "0.8"},
    ]
    out = sort_rows(rows)
    assert [(r["tier"], r["best_conf"]) for r in out] == [
        ("likely", "0.8"), ("likely", "0.5"), ("review", "0.9")]


def test_thumb_keeps_shape_and_fits():
    w, h = thumb_size(2704, 1520)
    assert w <= 600 and h <= 400
    assert abs(w / h - 2704 / 1520) < 0.02


def test_thumb_never_enlarges():
    assert thumb_size(100, 50) == (100, 50)


def test_dropdowns_cover_every_data_row_and_point_at_the_lists_sheet():
    names = ["Stop Signs 1022", "Pedestrian Traffic, (Symbol) 572", "School"]
    ws = make_wb(3, names)["review"]
    rules = {str(dv.sqref): dv.formula1 for dv in ws.data_validations.dataValidation}
    assert rules == {"E2:E4": f"Lists!$A$2:$A${len(DECISIONS) + 1}",
                     "F2:F4": "Lists!$B$2:$B$4"}


def test_option_lists_are_written_and_comma_names_stay_whole():
    names = ["Stop Signs 1022", "Pedestrian Traffic, (Symbol) 572"]
    lists = make_wb(1, names)["Lists"]
    assert [lists.cell(row=i, column=1).value for i in range(2, 6)] == DECISIONS
    assert [lists.cell(row=i, column=2).value for i in range(2, 4)] == names


def test_dropdowns_reject_bad_values_and_allow_blank():
    ws = make_wb(1, ["School"])["review"]
    for dv in ws.data_validations.dataValidation:
        assert dv.errorStyle == "stop"
        assert dv.showErrorMessage is True
        assert dv.allow_blank is True
        assert not dv.formula1.startswith("=")


def test_no_rows_means_no_rules_but_lists_still_written():
    wb = make_wb(0, ["School"])
    assert len(wb["review"].data_validations.dataValidation) == 0
    assert wb["Lists"].cell(row=2, column=2).value == "School"

def test_map_links_and_needs_location():
    lat, lon = "34.1", "-118.2"

    # Google Maps URL
    assert map_pin_url(lat, lon).endswith("query=34.1%2C-118.2")
    assert map_pin_url("", "") is None

    # Apple Maps URL
    apple_url = apple_maps_url(lat, lon, "School Sign")
    assert "maps.apple.com/place?" in apple_url
    assert "coordinate=34.100000,-118.200000" in apple_url
    # assert "name=School+Sign" in apple_url

    # Both map links should appear in their correct columns.
    ws = make_wb(1, ["School"], lat=lat, lon=lon)["review"]
    assert ws["G2"].value.startswith("=HYPERLINK(")
    assert ws["H2"].value == "Open in Apple Maps"
    expected_workbook_url = apple_maps_url(
    lat, lon, "Stop Signs 1022"
    )
    assert ws["H2"].hyperlink.target == expected_workbook_url

    # Missing location should be shown in both columns.
    ws = make_wb(1, ["School"])["review"]
    assert ws["G2"].value == "needs location"
    assert ws["H2"].value == "needs location"


def test_how_to_review_sheet_exists():
    assert "How to review" in make_wb(1, ["School"]).sheetnames


def test_load_class_names_decodes_apostrophe_and_ignores_choices(tmp_path):
    xml = tmp_path / "c.xml"
    xml.write_text('<View><RectangleLabels name="label" toName="image">'
                   '<Label value="TANP 7&#x27; HIGH"/><Label value="Stop"/>'
                   '</RectangleLabels><Choices name="c" toName="image">'
                   '<Choice value="clear"/></Choices></View>')
    assert load_class_names(str(xml)) == ["TANP 7' HIGH", "Stop"]

def test_catalog_match_and_mutcd_columns_are_filled_from_the_lookup():
    lookup = {
        "Stop Ahead": {
            "stock_number": "0161",
            "mutcd_code": "W3-1",
            "catalog_description": "Stop Ahead",
            "status": "matched in master catalog"
        }
    }

    rows = [{
        "group_id": "1",
        "tier": "likely",
        "label": "Stop Ahead",
        "n_sightings": "2",
        "best_conf": "0.8",
        "lat": "34.1",
        "lon": "-118.2",
        "best_picture": "x.jpg"
    }]

    ws = build_workbook(
        rows, ".", lambda p: None, ["Stop Ahead"], lookup
    )[0]["review"]

    # Headers
    assert ws["G1"].value == "Map pin"
    assert ws["H1"].value == "Apple Maps"
    assert ws["I1"].value == "Times seen"
    assert ws["J1"].value == "Lat"
    assert ws["K1"].value == "Lon"
    assert ws["L1"].value == "Group"
    assert ws["M1"].value == "Picture file"
    assert ws["N1"].value == "Catalog match"
    assert ws["O1"].value == "MUTCD code"

    # Row values
    assert ws["G2"].value.startswith("=HYPERLINK(")
    assert ws["H2"].hyperlink is not None
    assert ws["I2"].value == 2
    assert ws["J2"].value == 34.1
    assert ws["K2"].value == -118.2
    assert ws["L2"].value == 1
    assert ws["M2"].value == "x.jpg"
    assert ws["N2"].value == "0161 Stop Ahead"
    assert ws["O2"].value == "W3-1"