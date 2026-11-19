import pytest
from PIL import Image

from sign_context import (compass_word, crop_sign, is_near_diagonal,
                          suggest_side_and_facing)


def test_compass_word_buckets_and_wraparound():
    assert compass_word(0) == "North"
    assert compass_word(44) == "North"
    assert compass_word(46) == "East"
    assert compass_word(90) == "East"
    assert compass_word(180) == "South"
    assert compass_word(270) == "West"
    assert compass_word(359) == "North"
    assert compass_word(360) == "North"
    assert compass_word(-10) == "North"


def test_near_diagonal():
    assert is_near_diagonal(44)
    assert is_near_diagonal(135)
    assert not is_near_diagonal(0)
    assert not is_near_diagonal(186)


def test_side_heading_north():
    right = suggest_side_and_facing(0, 2000, 2704)
    left = suggest_side_and_facing(0, 500, 2704)
    assert right["side_of_street"] == "East"
    assert left["side_of_street"] == "West"
    assert right["faces_traffic"] == "North"


def test_side_heading_south_and_east():
    assert suggest_side_and_facing(180, 2000, 2704)["side_of_street"] == "West"
    assert suggest_side_and_facing(180, 500, 2704)["side_of_street"] == "East"
    assert suggest_side_and_facing(90, 2000, 2704)["side_of_street"] == "South"


def test_real_7th_st_stop_sign():
    # 7th St southbound, frame_000020s: Stop sign box 2118-2220 wide, camera
    # heading about 186 degrees. A southbound stop sign is on the west side.
    result = suggest_side_and_facing(186.3, (2118 + 2220) / 2, 2704)
    assert result["faces_traffic"] == "South"
    assert result["side_of_street"] == "West"
    assert result["note"] == ""


def test_diagonal_street_gets_a_note():
    assert "check" in suggest_side_and_facing(44, 2000, 2704)["note"]


def test_bad_frame_width():
    with pytest.raises(ValueError):
        suggest_side_and_facing(0, 10, 0)


def _frame(tmp_path, size=(2704, 1520)):
    path = tmp_path / "frame.jpg"
    Image.new("RGB", size, (90, 90, 90)).save(path)
    return str(path)


def test_crop_is_enlarged_with_margin(tmp_path):
    out = crop_sign(_frame(tmp_path), (2118, 661, 2220, 817),
                    str(tmp_path / "c.jpg"))
    with Image.open(out) as img:
        assert img.height == 300
        # box is 102 x 156; with 25% margin the crop is about 153 x 234
        assert abs(img.width / img.height - 153 / 234) < 0.03


def test_crop_is_clipped_at_the_frame_edge(tmp_path):
    out = crop_sign(_frame(tmp_path), (0, 0, 50, 50), str(tmp_path / "c.jpg"),
                    enhance=False)
    with Image.open(out) as img:
        # margin cannot go below 0, so the crop is 62 x 62 before enlarging
        assert img.size == (300, 300)


def test_big_crop_is_not_shrunk(tmp_path):
    out = crop_sign(_frame(tmp_path), (400, 300, 1200, 1100),
                    str(tmp_path / "c.jpg"), enhance=False)
    with Image.open(out) as img:
        assert img.height == 1200  # 800 box + 200 margin top and bottom


def test_bad_box_raises(tmp_path):
    with pytest.raises(ValueError):
        crop_sign(_frame(tmp_path), (50, 50, 40, 90), str(tmp_path / "c.jpg"))


# ---- new: wide-sign cap and the per-row helper ----

def test_wide_crop_is_capped_in_width(tmp_path):
    # a street-name-sign shape: 66 x 15
    out = crop_sign(_frame(tmp_path), (1128, 725, 1194, 740),
                    str(tmp_path / "c.jpg"), enhance=False)
    with Image.open(out) as img:
        assert img.width <= 600
        assert img.height < 300


def _run(tmp_path, heading="186.3"):
    (tmp_path / "frames").mkdir()
    Image.new("RGB", (2704, 1520), (90, 90, 90)).save(
        tmp_path / "frames" / "frame_000020s.jpg")
    row = {"group_id": "7", "best_frame": "frame_000020s.jpg",
           "x1": "2118", "y1": "661", "x2": "2220", "y2": "817",
           "cam_heading": heading}
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    return str(tmp_path), row, str(out_dir)


def test_row_context_full(tmp_path):
    from sign_context import sign_context_for_row
    run, row, out = _run(tmp_path)
    ctx = sign_context_for_row(run, row, out)
    assert ctx["crop"].endswith("crop_7.jpg")
    assert (ctx["side"], ctx["faces"]) == ("West", "South")


def test_row_context_old_run_without_heading(tmp_path):
    from sign_context import sign_context_for_row
    run, row, out = _run(tmp_path, heading="")
    ctx = sign_context_for_row(run, row, out)
    assert ctx["crop"] and ctx["side"] == "" and "heading" in ctx["note"]
    row.pop("cam_heading")                       # column absent entirely
    assert sign_context_for_row(run, row, out)["side"] == ""


def test_row_context_missing_frame_or_box_does_not_crash(tmp_path):
    from sign_context import sign_context_for_row
    run, row, out = _run(tmp_path)
    assert sign_context_for_row(run, dict(row, best_frame="nope.jpg"), out)["crop"] is None
    assert "box" in sign_context_for_row(run, dict(row, x1=""), out)["note"]