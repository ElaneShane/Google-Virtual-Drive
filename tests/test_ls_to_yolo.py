import pytest
from ls_to_yolo import (load_class_names, rect_to_yolo, pick_annotation,
                        parse_task, ls_image_path, resolve_image)


def test_rect_basic():
    v = {"x": 10, "y": 20, "width": 30, "height": 40}
    assert rect_to_yolo(v) == pytest.approx((0.25, 0.4, 0.3, 0.4))


def test_rect_is_clamped():
    v = {"x": -5, "y": 0, "width": 20, "height": 10}
    assert rect_to_yolo(v) == pytest.approx((0.075, 0.05, 0.15, 0.1))


def test_rect_zero_size_raises():
    with pytest.raises(ValueError):
        rect_to_yolo({"x": 50, "y": 50, "width": 0, "height": 10})


def test_config_names_in_order_ignoring_comments(tmp_path):
    p = tmp_path / "c.xml"
    p.write_text('<View><RectangleLabels name="l" toName="i">'
                 '<Label value="A"/><!-- note --><Label value="TANP 7\' HIGH"/>'
                 '<Label value="C"/></RectangleLabels></View>')
    assert load_class_names(str(p)) == ["A", "TANP 7' HIGH", "C"]


def test_pick_annotation_takes_last_not_cancelled():
    task = {"annotations": [{"id": 1}, {"id": 2}, {"id": 3, "was_cancelled": True}]}
    assert pick_annotation(task)["id"] == 2


def test_pick_annotation_none():
    assert pick_annotation({"annotations": []}) is None


def _task(label, extra=None):
    box = {"type": "rectanglelabels",
           "value": {"x": 10, "y": 20, "width": 30, "height": 40,
                     "rotation": 0, "rectanglelabels": [label]}}
    if extra:
        box["value"].update(extra)
    cond = {"type": "choices", "value": {"choices": ["hard"]}}
    return {"annotations": [{"result": [box, cond]}]}


def test_parse_task_good():
    ids = {"Stop Signs 1022": 0, "other_sign": 1}
    lines, cond, problems = parse_task(_task("Stop Signs 1022"), ids)
    assert lines == ["0 0.250000 0.400000 0.300000 0.400000"]
    assert cond == "hard" and problems == []


def test_parse_task_unknown_label_is_a_problem():
    lines, _, problems = parse_task(_task("Mystery"), {"other_sign": 0})
    assert lines == [] and len(problems) == 1


def test_parse_task_rotated_box_is_a_problem():
    _, _, problems = parse_task(_task("other_sign", {"rotation": 15}), {"other_sign": 0})
    assert len(problems) == 1


def test_image_path_maps_into_media_folder():
    p = ls_image_path("/data/upload/2/abc-frame_0001.jpg", "/m")
    assert p == "/m/upload/2/abc-frame_0001.jpg"


def test_image_path_rejects_other_kinds():
    with pytest.raises(ValueError):
        ls_image_path("/data/local-files/?d=x/y.jpg", "/m")

def test_resolve_upload_path():
    assert resolve_image("/data/upload/2/a.jpg", "/m", "/r") == "/m/upload/2/a.jpg"


def test_resolve_full_local_path_without_leading_slash():
    p = resolve_image("/data/local-files/?d=home/x/y.jpg", "/m", "/nonexistent")
    assert p == "/home/x/y.jpg"