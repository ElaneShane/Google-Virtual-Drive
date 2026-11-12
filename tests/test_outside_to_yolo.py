import pytest
from outside_to_yolo import cap_photos, rf_source_key, pick_one_copy, convert_rf_lines

IDS = {"Stop Signs 1022": 27, "School": 50}
RF = ["children_crossing", "greenLight", "stop"]


def test_source_key_strips_the_copy_code():
    assert rf_source_key("2023_0912_001_JPG.rf.abc123.jpg") == "2023_0912_001_JPG"


def test_source_key_without_rf_marker():
    assert rf_source_key("photo.jpg") == "photo"


def test_pick_one_copy_per_photo():
    files = ["a_JPG.rf.1.jpg", "a_JPG.rf.2.jpg", "a_JPG.rf.3.jpg", "b_JPG.rf.9.jpg"]
    picked = pick_one_copy(files, seed=0)
    assert set(picked) == {"a_JPG", "b_JPG"}
    assert picked["a_JPG"] in files[:3]
    assert picked["b_JPG"] == "b_JPG.rf.9.jpg"


def test_pick_one_copy_is_repeatable():
    files = ["a_JPG.rf.1.jpg", "a_JPG.rf.2.jpg", "a_JPG.rf.3.jpg"]
    assert pick_one_copy(files, seed=0) == pick_one_copy(files, seed=0)


def test_convert_maps_names_to_our_numbers():
    lines, skipped = convert_rf_lines("2 0.5 0.5 0.1 0.2\n", RF, IDS)
    assert lines == ["27 0.5 0.5 0.1 0.2"]
    assert skipped == 0


def test_convert_skips_and_counts_lights():
    lines, skipped = convert_rf_lines("1 0.1 0.2 0.3 0.4\n0 0.5 0.5 0.1 0.1\n", RF, IDS)
    assert lines == ["50 0.5 0.5 0.1 0.1"]
    assert skipped == 1


def test_convert_works_without_final_newline():
    lines, _ = convert_rf_lines("2 0.1 0.1 0.1 0.1\n0 0.2 0.2 0.2 0.2", RF, IDS)
    assert len(lines) == 2


def test_convert_unknown_roboflow_class_raises():
    with pytest.raises(ValueError):
        convert_rf_lines("0 0.5 0.5 0.1 0.1", ["mystery_sign"], IDS)


def test_convert_bad_line_raises():
    with pytest.raises(ValueError):
        convert_rf_lines("2 0.5 0.5", RF, IDS)


from outside_to_yolo import load_rf_names, load_roboflow


def make_rf(tmp_path):
    (tmp_path / "data.yaml").write_text("nc: 3\nnames: ['children_crossing', 'greenLight', 'stop']\n")
    for split in ("train", "valid", "test"):
        (tmp_path / split / "images").mkdir(parents=True)
        (tmp_path / split / "labels").mkdir(parents=True)
    return tmp_path


def add_photo(root, split, name, label_text):
    (root / split / "images" / f"{name}.jpg").write_bytes(b"x")
    (root / split / "labels" / f"{name}.txt").write_text(label_text)


def test_load_rf_names(tmp_path):
    make_rf(tmp_path)
    assert load_rf_names(str(tmp_path / "data.yaml")) == ["children_crossing", "greenLight", "stop"]


def test_load_roboflow_keeps_one_copy_and_drops_light_only(tmp_path):
    make_rf(tmp_path)
    add_photo(tmp_path, "train", "a_JPG.rf.1", "2 0.5 0.5 0.1 0.1")
    add_photo(tmp_path, "train", "a_JPG.rf.2", "2 0.5 0.5 0.1 0.1")
    add_photo(tmp_path, "train", "b_JPG.rf.1", "1 0.5 0.5 0.1 0.1")
    add_photo(tmp_path, "valid", "c_JPG.rf.1", "0 0.3 0.3 0.1 0.1\n1 0.6 0.6 0.1 0.1")
    kept, report = load_roboflow(str(tmp_path), {"Stop Signs 1022": 27, "School": 50})
    assert sorted(k["name"] for k in kept) == ["rf_a_JPG.jpg", "rf_c_JPG.jpg"]
    assert report["photos_seen"] == 4
    assert report["unique_photos"] == 3
    assert report["dropped_no_signs"] == 1
    assert report["light_boxes_skipped"] == 2
    c = [k for k in kept if k["name"] == "rf_c_JPG.jpg"][0]
    assert c["lines"] == ["50 0.3 0.3 0.1 0.1"]



from outside_to_yolo import convert_arts_xml, ARTS_TO_OURS

ARTS_IDS = {"Stop Signs 1022": 27, "speed_limit_sign": 40}


def arts_xml(objects, size="<width>1920</width><height>1080</height>"):
    objs = "".join(
        f"<object><name>{c}</name><bndbox><xmin>{a}</xmin><ymin>{b}</ymin>"
        f"<xmax>{x}</xmax><ymax>{y}</ymax></bndbox></object>" for c, a, b, x, y in objects)
    return f"<annotation><size>{size}</size>{objs}</annotation>"


def test_arts_maps_stop_box():
    lines, unmapped = convert_arts_xml(arts_xml([("R1-1", 960, 540, 1060, 640)]), ARTS_IDS)
    p = lines[0].split()
    assert p[0] == "27"
    assert [float(v) for v in p[1:]] == pytest.approx([1010 / 1920, 590 / 1080, 100 / 1920, 100 / 1080], abs=1e-5)
    assert unmapped == set()


def test_arts_reports_unmapped_code():
    lines, unmapped = convert_arts_xml(arts_xml([("VD-062", 0, 0, 50, 50)]), ARTS_IDS)
    assert lines == []
    assert unmapped == {"VD-062"}


def test_arts_mixed_photo_returns_both():
    lines, unmapped = convert_arts_xml(
        arts_xml([("R1-1", 10, 10, 60, 60), ("D3-1", 100, 100, 200, 150)]), ARTS_IDS)
    assert len(lines) == 1
    assert unmapped == {"D3-1"}


def test_arts_clamps_box_past_edge():
    lines, _ = convert_arts_xml(arts_xml([("R1-1", 1900, 100, 2000, 200)]), ARTS_IDS)
    p = [float(v) for v in lines[0].split()[1:]]
    assert p[0] == pytest.approx(1910 / 1920, abs=1e-5)
    assert p[2] == pytest.approx(20 / 1920, abs=1e-5)


def test_arts_zero_area_box_raises():
    with pytest.raises(ValueError):
        convert_arts_xml(arts_xml([("R1-1", 50, 50, 50, 90)]), ARTS_IDS)


def test_arts_missing_size_raises():
    with pytest.raises(ValueError):
        convert_arts_xml(arts_xml([("R1-1", 1, 1, 9, 9)], size=""), ARTS_IDS)


def test_arts_speed_codes_all_one_class():
    codes = ["R2-125", "R2-130", "R2-135", "R2-140", "R2-150"]
    assert {ARTS_TO_OURS[c] for c in codes} == {"speed_limit_sign"}
    assert "R2-165" not in ARTS_TO_OURS


from outside_to_yolo import load_arts


def test_load_arts_keeps_only_fully_mapped_photos(tmp_path):
    (tmp_path / "Annotations").mkdir()
    (tmp_path / "JPEGImages").mkdir()
    cases = {
        "p1": [("R1-1", 10, 10, 60, 60)],                          # kept
        "p2": [("R1-1", 10, 10, 60, 60), ("D3-1", 5, 5, 50, 50)],  # dropped: D3-1 unmapped
        "p3": [("VD-062", 5, 5, 50, 50)],                          # dropped: unmapped
    }
    for stem, objs in cases.items():
        (tmp_path / "Annotations" / f"{stem}.xml").write_text(arts_xml(objs))
        (tmp_path / "JPEGImages" / f"{stem}.jpg").write_bytes(b"x")
    kept, rep = load_arts(str(tmp_path), ARTS_IDS)
    assert [k["name"] for k in kept] == ["arts_p1.jpg"]
    assert rep["xml_seen"] == 3
    assert rep["dropped_unmapped"] == 2
    assert dict(rep["top_unmapped_codes"]) == {"D3-1": 1, "VD-062": 1}


    from outside_to_yolo import cap_photos


def photo(name, *classes):
    return {"name": name, "lines": [f"{c} 0.5 0.5 0.1 0.1" for c in classes]}


def test_cap_stops_at_limit():
    items = [photo(f"p{i}", 1) for i in range(5)]
    kept, totals = cap_photos(items, cap=3)
    assert len(kept) == 3
    assert totals[1] == 3


def test_cap_is_repeatable():
    items = [photo(f"p{i}", 1) for i in range(10)]
    a, _ = cap_photos(items, cap=4, seed=0)
    b, _ = cap_photos(items, cap=4, seed=0)
    assert [k["name"] for k in a] == [k["name"] for k in b]


def test_cap_prefers_photos_with_rare_classes():
    items = [photo(f"a{i}", 1) for i in range(5)] + [photo("x", 1, 2)]
    kept, _ = cap_photos(items, cap=2)
    assert "x" in [k["name"] for k in kept]
    assert len(kept) == 2


def test_cap_counts_what_we_already_have():
    items = [photo(f"p{i}", 1) for i in range(5)]
    kept, _ = cap_photos(items, cap=3, base_counts={1: 2})
    assert len(kept) == 1


def test_cap_class_override():
    items = [photo(f"p{i}", 7) for i in range(5)]
    kept, _ = cap_photos(items, cap=2, class_caps={7: 4})
    assert len(kept) == 4


from outside_to_yolo import apply_review

REV_IDS = {"other_sign": 35, "Stop Ahead": 52, "Yield Here to Pedestrians": 51,
           "Right Lane Must Turn Right": 53}


def make_review(tmp_path, label_text, csv_rows):
    (tmp_path / "labels" / "train").mkdir(parents=True)
    (tmp_path / "labels" / "train" / "pic1.txt").write_text(label_text)
    csv_file = tmp_path / "review.csv"
    csv_file.write_text("tile,split,image,line_in_label_file,xc,yc,w,h,choice\n" + csv_rows)
    return str(tmp_path), str(csv_file)


def test_review_renames_the_right_line(tmp_path):
    d, c = make_review(tmp_path, "27 0.1 0.1 0.1 0.1\n35 0.5 0.5 0.2 0.2\n",
                       "1,train,pic1,2,0.5,0.5,0.2,0.2, S\n")
    changes = apply_review(d, c, REV_IDS)
    assert changes["Stop Ahead"] == 1
    assert (tmp_path / "labels" / "train" / "pic1.txt").read_text() == \
        "27 0.1 0.1 0.1 0.1\n52 0.5 0.5 0.2 0.2\n"


def test_review_leaves_blank_and_D_alone(tmp_path):
    text = "35 0.5 0.5 0.2 0.2\n35 0.3 0.3 0.1 0.1\n"
    d, c = make_review(tmp_path, text,
                       "1,train,pic1,1,0.5,0.5,0.2,0.2,\n2,train,pic1,2,0.3,0.3,0.1,0.1, D\n")
    assert sum(apply_review(d, c, REV_IDS).values()) == 0
    assert (tmp_path / "labels" / "train" / "pic1.txt").read_text() == text


def test_review_refuses_a_line_that_is_not_other_sign(tmp_path):
    d, c = make_review(tmp_path, "27 0.5 0.5 0.2 0.2\n", "1,train,pic1,1,0.5,0.5,0.2,0.2,Y\n")
    with pytest.raises(ValueError):
        apply_review(d, c, REV_IDS)


def test_review_refuses_a_box_that_does_not_match(tmp_path):
    d, c = make_review(tmp_path, "35 0.5 0.5 0.2 0.2\n", "1,train,pic1,1,0.9,0.9,0.2,0.2,Y\n")
    with pytest.raises(ValueError):
        apply_review(d, c, REV_IDS)


def test_review_unknown_letter_raises(tmp_path):
    d, c = make_review(tmp_path, "35 0.5 0.5 0.2 0.2\n", "1,train,pic1,1,0.5,0.5,0.2,0.2,Q\n")
    with pytest.raises(ValueError):
        apply_review(d, c, REV_IDS)



from outside_to_yolo import read_yaml_names, remap_labels


def test_read_yaml_names():
    t = 'path: /x\nnames:\n  0: "A"\n  1: "No Parking Signs Letters"\n  2: "TANP 7\' HIGH"\n'
    assert read_yaml_names(t) == {0: "A", 1: "No Parking Signs Letters", 2: "TANP 7' HIGH"}


def test_remap_changes_shifted_numbers_by_name():
    old = {16: "No Parking Signs Letters", 26: "Stop Signs 1022"}
    ours = {"No Parking Signs Letters": 17, "Stop Signs 1022": 27}
    assert remap_labels("16 0.1 0.1 0.1 0.1\n26 0.2 0.2 0.2 0.2", old, ours) == \
        ["17 0.1 0.1 0.1 0.1", "27 0.2 0.2 0.2 0.2"]


def test_remap_unknown_name_raises():
    with pytest.raises(ValueError):
        remap_labels("1 0.1 0.1 0.1 0.1", {1: "Mystery"}, {"A": 0})


def test_remap_unknown_number_raises():
    with pytest.raises(ValueError):
        remap_labels("9 0.1 0.1 0.1 0.1", {1: "A"}, {"A": 0})


def test_remap_empty_label_stays_empty():
    assert remap_labels("", {1: "A"}, {"A": 0}) == []



from outside_to_yolo import load_streetview


def test_load_streetview_remaps_and_reports(tmp_path):
    (tmp_path / "data.yaml").write_text(
        'path: /x\ntrain: images/train\nnames:\n  0: "A"\n  1: "Stop Signs 1022"\n')
    (tmp_path / "images" / "train").mkdir(parents=True)
    (tmp_path / "labels" / "train").mkdir(parents=True)
    (tmp_path / "images" / "train" / "p1.jpg").write_bytes(b"x")
    (tmp_path / "images" / "train" / "p2.png").write_bytes(b"x")
    (tmp_path / "labels" / "train" / "p1.txt").write_text("1 0.5 0.5 0.1 0.1\n")
    (tmp_path / "labels" / "train" / "p2.txt").write_text("")
    (tmp_path / "labels" / "train" / "p3.txt").write_text("0 0.5 0.5 0.1 0.1\n")   # no picture
    items, rep = load_streetview(str(tmp_path), {"A": 0, "Stop Signs 1022": 27})
    assert sorted(i["name"] for i in items) == ["sv_p1.jpg", "sv_p2.png"]
    p1 = [i for i in items if i["name"] == "sv_p1.jpg"][0]
    assert p1["lines"] == ["27 0.5 0.5 0.1 0.1"]
    assert rep == {"labels_seen": 3, "no_picture": 1, "empty": 1}


def test_arts_challenging_codes_map():
    assert ARTS_TO_OURS["R10-11"] == "No Turn on Red"
    assert ARTS_TO_OURS["W17-1"] == "Speed humps -- W17-1"
    assert ARTS_TO_OURS["R7-2"] == "No Parking Signs Symbol"



from outside_to_yolo import make_alias_ids


def test_alias_points_merged_names_at_new_class():
    alias = make_alias_ids(["Street Cleaning Symbol", "Stop"],
                           {"NP MON": "Street Cleaning Symbol", "NP TUE": "Street Cleaning Symbol"})
    assert alias["NP MON"] == alias["NP TUE"] == 0
    assert alias["Stop"] == 1


def test_alias_rejects_unknown_target():
    with pytest.raises(ValueError):
        make_alias_ids(["A"], {"x": "B"})


def test_alias_leaves_dropped_names_out():
    assert "dnsot_sign" not in make_alias_ids(["A"], {})


def test_arts_code_map_override():
    xml = arts_xml([("R4-7", 10, 10, 60, 60)])
    lines, unmapped = convert_arts_xml(xml, {"R4-7 Keep Right Arrow": 9},
                                       code_map={"R4-7": "R4-7 Keep Right Arrow"})
    assert lines[0].split()[0] == "9"
    assert unmapped == set()
    lines, unmapped = convert_arts_xml(xml, {"R4-7 Keep Right Arrow": 9})
    assert unmapped == {"R4-7"}


from run_g_classes import build_new_names


def test_merges_drops_and_appends():
    old = ["A", "X1", "X2", "gone", "B"]
    new = build_new_names(old, rename={"X1": "X", "X2": "X"}, dropped=["gone"], extra=["E"])
    assert new == ["A", "B", "X", "E"]

def test_merge_target_already_in_old_list_is_not_duplicated():
    assert build_new_names(["A", "Y1", "Y"], {"Y1": "Y"}, [], []) == ["A", "Y"]


def test_unknown_old_name_raises():
    with pytest.raises(ValueError):
        build_new_names(["A"], {"typo": "X"}, [], [])