import torch
import pytest
from helper import get_box_depth_and_bearing, specifySigns

def test_box_depth_is_median_inside_box():
    depth = torch.zeros(100, 200)
    depth[20:40, 50:90] = 7.0
    d, b = get_box_depth_and_bearing(depth, [50, 20, 90, 40], 270, 90)
    assert d == pytest.approx(7.0)
    assert b == pytest.approx(256.5)      # box center x=70 -> offset -0.15 -> 270 - 13.5

def test_box_is_clamped_to_image():
    depth = torch.ones(100, 200)
    d, b = get_box_depth_and_bearing(depth, [-10, -10, 300, 150], 0, 90)
    assert d == pytest.approx(1.0)
    assert b == pytest.approx(0)

def test_ocr_empty_words_returns_nothing():
    cands = [{"Bounding box name": "Hourly", "OCR Desc": "1 HOUR PARKING"}]
    assert specifySigns("Hourly", [], cands) == ("", {})

def test_ocr_picks_lowest_cer_and_ignores_other_signs():
    cands = [
        {"Bounding box name": "Hourly", "OCR Desc": "1 HOUR PARKING"},
        {"Bounding box name": "Hourly", "OCR Desc": "2 HOUR PARKING"},
        {"Bounding box name": "Tow",    "OCR Desc": "2 HOUR PARKING"},
    ]
    best, cers = specifySigns("Hourly", ["2", "HOUR", "PARKING"], cands)
    assert best == "2 hour parking"       # specifySigns applies .capitalize()
    assert len(cers) == 2                 # the "Tow" entry was skipped