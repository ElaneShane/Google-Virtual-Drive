def polygon_to_box(line):
    """One label line -> (class_id, x_center, y_center, width, height), all 0 to 1.
    A polygon line is: class x1 y1 x2 y2 ... (at least 3 points).
    A line that is already a box (4 numbers) passes through."""
    parts = line.split()
    if len(parts) < 5:
        raise ValueError(f"Label line too short: {line!r}")
    cls = int(parts[0])
    nums = [float(v) for v in parts[1:]]

    if len(nums) == 4:                      # already x_center y_center w h
        return cls, nums[0], nums[1], nums[2], nums[3]
    if len(nums) < 6 or len(nums) % 2 != 0: # a polygon needs pairs, and 3+ points
        raise ValueError(f"Bad coordinate count ({len(nums)}): {line!r}")

    xs = [min(max(v, 0.0), 1.0) for v in nums[0::2]]   # x values, clamped to 0..1
    ys = [min(max(v, 0.0), 1.0) for v in nums[1::2]]   # y values, clamped to 0..1
    x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Empty box: {line!r}")
    return cls, (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1


def convert_label_text(text):
    """A whole label file -> (list of YOLO box lines, list of bad lines)."""
    good, bad = [], []
    for ln in text.splitlines():
        if not ln.strip():
            continue
        try:
            c, xc, yc, w, h = polygon_to_box(ln)
            good.append(f"{c} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")
        except ValueError:
            bad.append(ln)
    return good, bad