import pytest
from label_convert import polygon_to_box, convert_label_text

def test_rectangle():
    assert polygon_to_box("3 0.1 0.2 0.5 0.2 0.5 0.6 0.1 0.6") == pytest.approx((3, 0.3, 0.4, 0.4, 0.4))

def test_tilted_triangle():
    assert polygon_to_box("1 0.2 0.2 0.4 0.3 0.3 0.5") == pytest.approx((1, 0.3, 0.35, 0.2, 0.3))

def test_values_are_clamped():
    assert polygon_to_box("0 -0.1 0.5 1.2 0.5 0.5 0.9") == pytest.approx((0, 0.5, 0.7, 1.0, 0.4))

def test_box_line_passes_through():
    assert polygon_to_box("2 0.5 0.5 0.2 0.1") == pytest.approx((2, 0.5, 0.5, 0.2, 0.1))

def test_odd_number_of_values_raises():
    with pytest.raises(ValueError):
        polygon_to_box("0 0.1 0.2 0.3 0.4 0.5 0.6 0.7")
        
def test_too_few_points_raises():
    with pytest.raises(ValueError):
        polygon_to_box("0 0.1 0.2 0.3")


def test_file_converter_collects_bad_lines():
    good, bad = convert_label_text("0 0.1 0.1 0.5 0.1 0.5 0.5\n\n7 0.1\n")
    assert len(good) == 1 and len(bad) == 1