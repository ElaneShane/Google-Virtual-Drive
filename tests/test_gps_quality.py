import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from gps_quality import check_hops, find_bad_points

M_PER_DEG = 111320.0

def make_track(times, offsets=None):
    """Fake GPS: truck driving north at 10 m/s. offsets = {time: extra meters} adds a bad point."""
    offsets = offsets or {}
    rows = []
    for t in times:
        lat = 34.0 + (10.0 * t + offsets.get(t, 0)) / M_PER_DEG
        rows.append((float(t), 0.0, lat, -118.0, 3, 1.8, 10.0))
    return rows

def run(track):
    return find_bad_points(track, check_hops(track))

def test_clean_track_has_no_bad_points():
    bad, questionable = run(make_track(range(0, 8)))
    assert bad == set() and questionable == set()

def test_first_point_after_dropout_is_bad():
    track = make_track([0, 1, 2, 3, 10, 11, 12, 13], offsets={10: 40})
    bad, _ = run(track)
    assert bad == {10.0}

def test_point_with_flagged_hops_on_both_sides_is_bad():
    track = make_track(range(0, 7), offsets={3: 30})
    bad, _ = run(track)
    assert bad == {3.0}