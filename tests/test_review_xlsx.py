from review_xlsx import (sort_rows, thumb_size, build_workbook, load_class_names,
                         DECISIONS, map_pin_url)


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
    assert w <= 420 and h <= 240
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


def test_map_pin_url_and_needs_location():
    assert map_pin_url("34.1", "-118.2").endswith("query=34.1%2C-118.2")
    assert map_pin_url("", "") is None
    ws = make_wb(1, ["School"], lat="34.1", lon="-118.2")["review"]
    assert ws["G2"].value.startswith("=HYPERLINK(")
    ws = make_wb(1, ["School"])["review"]
    assert ws["G2"].value == "needs location"


def test_how_to_review_sheet_exists():
    assert "How to review" in make_wb(1, ["School"]).sheetnames


def test_load_class_names_decodes_apostrophe_and_ignores_choices(tmp_path):
    xml = tmp_path / "c.xml"
    xml.write_text('<View><RectangleLabels name="label" toName="image">'
                   '<Label value="TANP 7&#x27; HIGH"/><Label value="Stop"/>'
                   '</RectangleLabels><Choices name="c" toName="image">'
                   '<Choice value="clear"/></Choices></View>')
    assert load_class_names(str(xml)) == ["TANP 7' HIGH", "Stop"]