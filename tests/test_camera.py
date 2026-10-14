from camera import yaw_for_clip
from geo import sign_bearing
import pytest
from camera import lookup_hfov


def test_hero10_linear_high():
    assert lookup_hfov("HERO10 Black", "Linear", "HS High") == 87.0


def test_hero9_wide():
    assert lookup_hfov("HERO9 Black", "Wide", "HS EIS") == 109.0


def test_unknown_camera_stops():
    with pytest.raises(ValueError):
        lookup_hfov("HERO11 Black", "Linear", "HS High")


def test_missing_tags_stops():
    with pytest.raises(ValueError):
        lookup_hfov(None, None, None)


def test_yaw_found(tmp_path):
    f = tmp_path / "s.csv"
    f.write_text("clip,yaw_deg,status\nA.MP4,90,assumed\n")
    assert yaw_for_clip("/some/folder/A.MP4", str(f)) == (90.0, "assumed")


def test_yaw_missing_clip_stops(tmp_path):
    f = tmp_path / "s.csv"
    f.write_text("clip,yaw_deg,status\nA.MP4,90,assumed\n")
    with pytest.raises(ValueError):
        yaw_for_clip("B.MP4", str(f))


def test_yaw_unknown_stops(tmp_path):
    f = tmp_path / "s.csv"
    f.write_text("clip,yaw_deg,status\nA.MP4,,unknown\n")
    with pytest.raises(ValueError):
        yaw_for_clip("A.MP4", str(f))


def test_sidewalk_camera_points_right_of_travel():
    # truck drives north (0), camera turned 90 deg right, sign dead center -> sign is east (90)
    assert sign_bearing((0 + 90) % 360, 960, 1920, 109.0) == 90.0