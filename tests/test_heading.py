import pytest
from pyproj import Geod
from geo import heading_from_track, fill_missing_headings


def make_track(legs):
    """Fake GPS track, 1 point per second. legs = [(bearing, seconds), ...].
    Truck moves 10 m/s in the bearing direction; bearing None means stopped."""
    geod = Geod(ellps="WGS84")
    lat, lon = 34.0, -118.0
    track = [(0.0, lat, lon)]
    t = 0.0
    for bearing, secs in legs:
        for _ in range(secs):
            if bearing is not None:
                lon, lat, _ = geod.fwd(lon, lat, bearing, 10.0)
            t += 1
            track.append((t, lat, lon))
    return track


def test_straight_line():
    assert heading_from_track(make_track([(90, 20)]), 10) == pytest.approx(90, abs=0.5)


def test_turn_uses_the_direction_at_the_frame():
    track = make_track([(45, 10), (135, 10)])    # northeast, then southeast
    assert heading_from_track(track, 3) == pytest.approx(45, abs=1)
    assert heading_from_track(track, 17) == pytest.approx(135, abs=1)
    assert 80 < heading_from_track(track, 10) < 100   # at the corner: in between


def test_stopped_truck_gives_none():
    assert heading_from_track(make_track([(None, 20)]), 10) is None


def test_stopped_then_moving_widens_the_window():
    track = make_track([(None, 5), (90, 15)])    # sits 5 s, then drives east
    assert heading_from_track(track, 1) == pytest.approx(90, abs=1)


def test_fill_missing_headings():
    assert fill_missing_headings([None, 10, None, 20]) == [10, 10, 10, 20]


def test_fill_all_missing_raises():
    with pytest.raises(ValueError):
        fill_missing_headings([None, None])