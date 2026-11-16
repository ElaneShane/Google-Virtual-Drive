from review_xlsx import sort_rows, thumb_size


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

from review_xlsx import (sort_rows, thumb_size, build_workbook, load_class_names,
                         add_dropdowns, DECISIONS)

def fake_row(i):
    return {"group_id": str(i), "tier": "likely", "label": "Stop Signs 1022",
            "n_sightings": "2", "best_conf": "0.8", "lat": "", "lon": "",
            "best_picture": "x.jpg"}


def make_sheet(n_rows, names):
    rows = [fake_row(i) for i in range(n_rows)]
    wb, _ = build_workbook(rows, ".", lambda p: None, names)
    return wb.active


def test_dropdowns_cover_every_data_row_and_point_at_the_lists():
    names = ["Stop Signs 1022", "Pedestrian Traffic, (Symbol) 572", "School"]
    ws = make_sheet(3, names)
    rules = {str(dv.sqref): dv.formula1 for dv in ws.data_validations.dataValidation}
    assert rules == {"I2:I4": f"$M$2:$M${len(DECISIONS) + 1}",
                     "J2:J4": "$N$2:$N$4"}


def test_option_lists_are_written_and_comma_names_stay_whole():
    names = ["Stop Signs 1022", "Pedestrian Traffic, (Symbol) 572"]
    ws = make_sheet(1, names)
    assert [ws.cell(row=i, column=13).value for i in range(2, 6)] == DECISIONS
    assert [ws.cell(row=i, column=14).value for i in range(2, 4)] == names


def test_dropdowns_reject_bad_values_and_allow_blank():
    ws = make_sheet(1, ["School"])
    for dv in ws.data_validations.dataValidation:
        assert dv.errorStyle == "stop"
        assert dv.showErrorMessage is True
        assert dv.allow_blank is True
        assert not dv.formula1.startswith("=")


def test_no_rows_means_no_rules_but_lists_still_written():
    ws = make_sheet(0, ["School"])
    assert len(ws.data_validations.dataValidation) == 0
    assert ws.cell(row=2, column=14).value == "School"


def test_load_class_names_decodes_apostrophe_and_ignores_choices(tmp_path):
    xml = tmp_path / "c.xml"
    xml.write_text('<View><RectangleLabels name="label" toName="image">'
                   '<Label value="TANP 7&#x27; HIGH"/><Label value="Stop"/>'
                   '</RectangleLabels><Choices name="c" toName="image">'
                   '<Choice value="clear"/></Choices></View>')
    assert load_class_names(str(xml)) == ["TANP 7' HIGH", "Stop"]