from review_xlsx import sort_rows, thumb_size


def test_likely_comes_before_review_then_by_confidence():
    rows = [
        {"tier": "review", "best_conf": "0.9"},
        {"tier": "likely", "best_conf": "0.5"},
        {"tier": "likely", "best_conf": "0.8"},
    ]
    out = sort_rows(rows)
    assert [(r["tier"], r["best_conf"]) for r in out] == [
        ("likely", "0.8"), ("likely", "0.5"), ("review", "0.9")]


def test_thumb_keeps_shape_and_fits():
    w, h = thumb_size(2704, 1520)
    assert w <= 420 and h <= 240
    assert abs(w / h - 2704 / 1520) < 0.02


def test_thumb_never_enlarges():
    assert thumb_size(100, 50) == (100, 50)