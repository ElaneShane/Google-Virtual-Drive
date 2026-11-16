from group_detections import build_groups, assign_tier

def s(t, label, conf, depth=None, lat=None, lon=None):
    return {"frame": f"frame_{int(t):06d}s.jpg", "t": float(t), "label": label,
            "conf": conf, "depth": depth, "lat": lat, "lon": lon}

STOP = "Stop Signs 1022"

def test_no_gps_trio_is_one_group():           # frames 58, 62, 64
    g = build_groups([s(58, STOP, .41), s(62, STOP, .89), s(64, STOP, .89)], 2)
    assert len(g) == 1

def test_two_boxes_in_one_frame_never_merge():  # the two reflectors in frame 2
    refl = "Diamond Yellow Reflector 0215"
    g = build_groups([s(2, refl, .85, 14.05, 34.19644, -118.29813),
                      s(2, refl, .65, 14.05, 34.19632, -118.29804)], 2)
    assert len(g) == 2

def test_different_classes_do_not_merge():
    g = build_groups([s(10, STOP, .9), s(12, "No U-Turn", .9)], 2)
    assert len(g) == 2

def test_time_gate_separates_far_apart_sightings():
    g = build_groups([s(18, STOP, .9), s(120, STOP, .9)], 2)
    assert len(g) == 2

def test_sign_a_merges():
    g = build_groups([s(18, STOP, .91, 48.48, 34.196722, -118.298593),
                      s(20, STOP, .92, 35.65, 34.196791, -118.298491),
                      s(22, STOP, .91, 21.31, 34.196784, -118.298451)], 2)
    assert len(g) == 1

def test_sign_b_merges_despite_noisy_far_positions():
    g = build_groups([s(96, STOP, .55, 60.87, 34.197477, -118.303656),
                      s(98, STOP, .81, 52.97, 34.196868, -118.303999),
                      s(100, STOP, .93, 36.39, 34.196744, -118.304159),
                      s(102, STOP, .88, 17.85, 34.197017, -118.304141)], 2)
    assert len(g) == 1

def test_two_close_signs_at_same_time_split_by_position():
    g = build_groups([s(10, STOP, .9, 15, 34.20000, -118.30000),
                      s(12, STOP, .9, 10, 34.20100, -118.30000)], 2)   # about 111 m apart
    assert len(g) == 2

def test_tiers():
    one = [s(10, STOP, .9)]
    two = [s(10, STOP, .9), s(12, STOP, .8)]
    weak = [s(10, STOP, .30)]
    junk = [s(10, STOP, .10)]
    assert assign_tier(two) == "likely"
    assert assign_tier(one) == "review"
    assert assign_tier(weak) == "review"
    assert assign_tier(junk) == "dropped"


from group_detections import merge_duplicates, picture_path


def _s(frame, label, conf, box):
    return {"frame": frame, "t": 2.0, "label": label, "conf": conf,
            "depth": None, "lat": None, "lon": None, "box": box}


def test_real_name_beats_other_sign():
    a = _s("frame_000002s.jpg", "other_sign", 0.533, (0, 0, 100, 100))
    b = _s("frame_000002s.jpg", "Stop Ahead", 0.436, (1, 1, 101, 101))
    out = merge_duplicates([a, b])
    assert len(out) == 1
    assert out[0]["label"] == "Stop Ahead"
    assert out[0]["conf"] == 0.436


def test_same_name_duplicate_keeps_stronger():
    a = _s("frame_000026s.jpg", "Street Name Sign 4215", 0.583, (0, 0, 100, 100))
    b = _s("frame_000026s.jpg", "Street Name Sign 4215", 0.561, (20, 0, 120, 100))
    out = merge_duplicates([a, b])
    assert len(out) == 1
    assert out[0]["conf"] == 0.583


def test_far_apart_boxes_stay_separate():
    a = _s("frame_000002s.jpg", "Stop Signs 1022", 0.9, (0, 0, 50, 50))
    b = _s("frame_000002s.jpg", "Stop Signs 1022", 0.8, (500, 500, 550, 550))
    assert len(merge_duplicates([a, b])) == 2


def test_different_frames_never_merge():
    a = _s("frame_000002s.jpg", "Stop Signs 1022", 0.9, (0, 0, 50, 50))
    b = _s("frame_000004s.jpg", "Stop Signs 1022", 0.8, (0, 0, 50, 50))
    assert len(merge_duplicates([a, b])) == 2


def test_two_real_names_set_conflict_flag():
    a = _s("frame_000002s.jpg", "Stop Signs 1022", 0.9, (0, 0, 100, 100))
    b = _s("frame_000002s.jpg", "Do Not Enter Sign", 0.6, (0, 0, 100, 100))
    out = merge_duplicates([a, b])
    assert len(out) == 1
    assert out[0]["label"] == "Stop Signs 1022"
    assert out[0]["conflict"] is True


def test_thin_box_inside_taller_box_same_name_merges():
    # frame 26's strongest box sits inside two looser boxes
    a = _s("frame_000026s.jpg", "Street Name Sign 4215", 0.826, (1304, 774, 1353, 788))
    b = _s("frame_000026s.jpg", "Street Name Sign 4215", 0.583, (1301, 756, 1353, 783))
    c = _s("frame_000026s.jpg", "Street Name Sign 4215", 0.561, (1299, 765, 1352, 785))
    out = merge_duplicates([a, b, c])
    assert len(out) == 1
    assert out[0]["conf"] == 0.826


def test_inside_rule_needs_same_name():
    a = _s("frame_000038s.jpg", "Street Name Sign 4215", 0.74, (0, 0, 50, 14))
    b = _s("frame_000038s.jpg", "No Left Turn", 0.6, (0, 0, 50, 30))
    assert len(merge_duplicates([a, b])) == 2


def test_picture_path_high_confidence_uses_original_name():
    s = {"label": "speed_limit_sign", "raw_label": "15 MPH -- 0430",
         "conf": 0.971, "frame": "frame_000128s.jpg"}
    assert picture_path(s) == "detections/15 MPH -- 0430_High_Confidence/frame_000128s.jpg"


def test_picture_path_weak_box_goes_to_low_folder():
    s = {"label": "speed_limit_sign", "raw_label": "speed_limit_sign",
         "conf": 0.295, "frame": "frame_000104s.jpg"}
    assert picture_path(s) == "detections/speed_limit_sign_Low_Confidence/frame_000104s.jpg"