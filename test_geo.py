import pytest
from geo import sign_bearing, adjustCoords, calculate_bearing

# --- sign_bearing: car faces west (270), 1920 px wide, 90 deg horizontal FOV ---
def test_centered_sign_is_straight_ahead():
    assert sign_bearing(270, 960, 1920, 90) == pytest.approx(270)

def test_right_edge_adds_half_fov():
    assert sign_bearing(270, 1920, 1920, 90) == pytest.approx(315)

def test_left_edge_subtracts_half_fov():
    assert sign_bearing(270, 0, 1920, 90) == pytest.approx(225)

def test_wraps_past_north():
    assert sign_bearing(350, 1920, 1920, 90) == pytest.approx(35)   # 350 + 45 = 395

def test_wraps_below_zero():
    assert sign_bearing(10, 0, 1920, 90) == pytest.approx(325)      # 10 - 45 = -35

# --- calculate_bearing (car heading from two GPS points) ---
def test_north():
    assert calculate_bearing(34.0, -118.0, 34.001, -118.0) == pytest.approx(0, abs=0.1)

def test_east():
    assert calculate_bearing(34.0, -118.0, 34.0, -117.999) == pytest.approx(90, abs=0.5)

def test_west():
    assert calculate_bearing(34.0, -118.0, 34.0, -118.001) == pytest.approx(270, abs=0.5)

# --- adjustCoords: "start here, go this direction, this far" ---
def test_100m_north():
    lat, lon = adjustCoords(34.0, -118.0, 0, 100)
    assert lat == pytest.approx(34.0009, abs=2e-5)
    assert lon == pytest.approx(-118.0, abs=1e-6)

def test_west_facing_sign_lands_west():
    lat, lon = adjustCoords(34.0, -118.0, 270, 20)
    assert lon < -118.0
    assert lat == pytest.approx(34.0, abs=1e-4)