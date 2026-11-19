import csv
import math
import re

# ---- SETTINGS (all guesses, tuned by eye on two signs; check on more clips) ----
GATE_INTERVALS = 3        # link sightings only if within 3 x the frame interval in time
FAR_DEPTH_M = 45          # deeper than this, position is too noisy to judge
POS_BASE_M = 15           # position tolerance = base + per_depth * depth
POS_PER_DEPTH = 0.6
LIKELY_MIN_SIGHTINGS = 2  # tier rules
LIKELY_MIN_CONF = 0.4
REVIEW_MIN_CONF = 0.25
SAME_CLASS = {"15 MPH -- 0430": "speed_limit_sign"}   # names that mean the same thing
DUP_IOU = 0.5             # two boxes in one frame overlapping this much = one sign
DUP_INSIDE = 0.6          # same name, this much of the smaller box inside the other = one sign
def canon(label):
    return SAME_CLASS.get(label, label)


def frame_seconds(frame_name):
    """'frame_000058s.jpg' -> 58.0"""
    m = re.search(r"frame_(\d+)s", frame_name)
    if not m:
        raise ValueError(f"Cannot read the time from frame name: {frame_name}")
    return float(m.group(1))


def _float_or_none(text):
    text = (text or "").strip()
    return float(text) if text else None


def read_sightings(csv_path):
    """Read debug_detections.csv into a list of sighting dicts."""
    out = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            out.append({
                "frame": row["frame"],
                "t": frame_seconds(row["frame"]),
                "label": canon(row["label"]),
                "raw_label": row["label"],
                "conf": float(row["confidence"]),
                "depth": _float_or_none(row["depth_m"]),
                "lat": _float_or_none(row["sign_lat"]),
                "lon": _float_or_none(row["sign_lon"]),
                "box": (float(row["x1"]), float(row["y1"]),
                        float(row["x2"]), float(row["y2"])),
                "heading": _float_or_none(row.get("cam_heading")),
            })
    return out


def meters_between(lat1, lon1, lat2, lon2):
    """Flat-earth distance in meters. Fine for points a few hundred meters apart."""
    dy = (lat2 - lat1) * 111_000
    dx = (lon2 - lon1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def has_trusted_position(s):
    return (s["lat"] is not None and s["lon"] is not None
            and s["depth"] is not None and s["depth"] <= FAR_DEPTH_M)


def group_position_member(group):
    """The group's closest trusted sighting (closest = best position), or None."""
    trusted = [m for m in group if has_trusted_position(m)]
    return min(trusted, key=lambda m: m["depth"]) if trusted else None


def can_join(group, s, gate_s):
    if group[0]["label"] != s["label"]:
        return False                                   # rule 1: same class only
    if any(m["t"] == s["t"] for m in group):
        return False                                   # rule 2: never twice in one frame
    if s["t"] - max(m["t"] for m in group) > gate_s:
        return False                                   # rule 3: time gate
    anchor = group_position_member(group)
    if anchor is not None and has_trusted_position(s):  # rule 4: position gate
        limit = POS_BASE_M + POS_PER_DEPTH * max(anchor["depth"], s["depth"])
        if meters_between(anchor["lat"], anchor["lon"], s["lat"], s["lon"]) > limit:
            return False
    return True                                        # rule 5: otherwise link by time

def box_overlap(a, b):
    """How much two boxes overlap: 0 = not at all, 1 = identical."""
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = ((a[2] - a[0]) * (a[3] - a[1])
             + (b[2] - b[0]) * (b[3] - b[1]) - inter)
    return inter / union if union > 0 else 0.0

def inside_fraction(a, b):
    """How much of the smaller box lies inside the other: 0 = none, 1 = fully inside."""
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return (ix * iy) / smaller if smaller > 0 else 0.0

def merge_duplicates(sightings):
    """Boxes in the same frame that sit on top of each other become one sighting."""
    kept = []
    for s in sorted(sightings, key=lambda x: -x["conf"]):   # strongest first
        twin = None
        if s.get("box"):
            for k in kept:
                if (k["frame"] == s["frame"] and k.get("box")
        and (box_overlap(k["box"], s["box"]) >= DUP_IOU
                or (k["label"] == s["label"]
                    and inside_fraction(k["box"], s["box"]) >= DUP_INSIDE))):
                    twin = k
                    break
        if twin is None:
            kept.append(dict(s))
        elif twin["label"] == "other_sign" and s["label"] != "other_sign":
            twin.update(s)                 # real name beats other_sign
        elif s["label"] != twin["label"] and s["label"] != "other_sign":
            twin["conflict"] = True        # two real names disagree
        # otherwise s is just a weaker copy: drop it
    return kept

def build_groups(sightings, interval):
    """Walk through sightings in time order; join an open group or start a new one."""
    sightings = merge_duplicates(sightings)
    gate_s = GATE_INTERVALS * interval
    groups = []
    for s in sorted(sightings, key=lambda x: (x["t"], -x["conf"])):
        options = [g for g in groups if can_join(g, s, gate_s)]
        if options:
            # join the group that was seen most recently
            min_gap = min(s["t"] - max(m["t"] for m in g) for g in options)
            best = [g for g in options if s["t"] - max(m["t"] for m in g) == min_gap][0]
            best.append(s)
        else:
            groups.append([s])
    return groups


def assign_tier(group):
    n_frames = len({m["t"] for m in group})
    best = max(m["conf"] for m in group)
    if best < REVIEW_MIN_CONF:
        return "dropped"
    if n_frames >= LIKELY_MIN_SIGHTINGS and best >= LIKELY_MIN_CONF:
        return "likely"
    return "review"

def picture_path(s):
    """Where the picture with the boxes drawn is, relative to the run folder."""
    kind = "High" if s["conf"] >= 0.4 else "Low"      # matches the folder names in helper.py
    name = s.get("raw_label", s["label"])
    return f"detections/{name}_{kind}_Confidence/{s['frame']}"

def summarize(group, group_id):
    best_conf = max(group, key=lambda m: m["conf"])
    anchor = group_position_member(group)
    return {
        "group_id": group_id,
        "tier": assign_tier(group),
        "label": group[0]["label"],
        "n_sightings": len({m["t"] for m in group}),
        "best_conf": round(best_conf["conf"], 3),
        "best_frame": best_conf["frame"],
        "best_picture": picture_path(best_conf),
        "first_frame": min(group, key=lambda m: m["t"])["frame"],
        "last_frame": max(group, key=lambda m: m["t"])["frame"],
        "lat": anchor["lat"] if anchor else "",
        "lon": anchor["lon"] if anchor else "",
        "depth_m": anchor["depth"] if anchor else "",
        "reviewer_decision": "",
        "reviewer_label": "",
        "x1": (best_conf.get("box") or ("",)*4)[0], "y1": (best_conf.get("box") or ("",)*4)[1],
        "x2": (best_conf.get("box") or ("",)*4)[2], "y2": (best_conf.get("box") or ("",)*4)[3],
        "cam_heading": "" if best_conf.get("heading") is None else best_conf["heading"],
    }


REVIEW_FIELDS = ["group_id", "tier", "label", "n_sightings", "best_conf", "best_frame", "best_picture",
                 "first_frame", "last_frame", "lat", "lon", "depth_m", "x1", "y1", "x2", "y2", "cam_heading",
                 "reviewer_decision", "reviewer_label"]


def write_review(groups, out_path):
    rows = [summarize(g, i + 1) for i, g in enumerate(groups)]
    rows = [r for r in rows if r["tier"] != "dropped"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return rows