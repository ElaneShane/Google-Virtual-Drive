"""Helpers for the review sheet: a zoomed crop of one sign, and a suggested
"side of street" and "direction the sign faces".

"""
import os

from PIL import Image, ImageFilter, ImageOps

COMPASS = ["North", "East", "South", "West"]
BORDERLINE_DEG = 10  # within this many degrees of a diagonal: say "check"


def compass_word(degrees):
    """Turn a heading in degrees (0 = north, 90 = east) into North/East/South/West."""
    deg = degrees % 360
    return COMPASS[int(((deg + 45) % 360) // 90)]


def is_near_diagonal(degrees):
    """True if the heading is close to NE, SE, SW or NW (45, 135, 225, 315),
    where the four-word answer could easily be wrong."""
    deg = degrees % 360
    distance = min(abs(deg - d) for d in (45, 135, 225, 315))
    return distance <= BORDERLINE_DEG


def suggest_side_and_facing(camera_heading, x_center, frame_width):
    """Suggest which side of the street a sign is on, and which way it faces.

    camera_heading: direction the camera points, in degrees (0 = north).
    x_center: horizontal centre of the sign's box, in pixels.
    frame_width: width of the frame, in pixels.

    Side of street: a sign in the right half of the picture is on the right
    side of the truck, so we turn the heading 90 degrees clockwise to name it.
    A sign in the left half is on the left side, so we turn 90 degrees the
    other way. (Heading north, sign on the right: East side.)

    Faces traffic: we can see the front of the sign, so it faces drivers going
    the same way as the truck. (Heading south: South.)

    Returns a dict: side_of_street, faces_traffic, note.
    """
    if frame_width <= 0:
        raise ValueError("frame_width must be positive")
    on_right = x_center >= frame_width / 2
    side_heading = camera_heading + (90 if on_right else -90)
    note = ""
    if is_near_diagonal(camera_heading):
        note = "street runs diagonally - check"
    return {
        "side_of_street": compass_word(side_heading),
        "faces_traffic": compass_word(camera_heading),
        "note": note,
    }


def crop_sign(frame_path, box, out_path, margin=0.25, target_height=300,
              max_width=600, enhance=True):
    """Cut one sign out of the ORIGINAL frame, with a margin, and enlarge it.

    box: (x1, y1, x2, y2) in pixels of the original frame.
    margin: extra space around the box, as a fraction of the box size.
    target_height: crops shorter than this are enlarged to this height.
    max_width: but never so much that the crop gets wider than this (street
    name signs are very wide and thin).
    A crop that is already big enough is left at its size (never shrunk).
    enhance: gentle contrast stretch and sharpening. This makes the sign
    easier to look at. It cannot add detail that the camera never captured.

    Returns out_path. Raises ValueError for an empty or backwards box.
    """
    x1, y1, x2, y2 = box
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"bad box: {box}")
    with Image.open(frame_path) as frame:
        frame = frame.convert("RGB")
        width, height = frame.size
        pad_x = (x2 - x1) * margin
        pad_y = (y2 - y1) * margin
        left = max(0, int(x1 - pad_x))
        top = max(0, int(y1 - pad_y))
        right = min(width, int(x2 + pad_x))
        bottom = min(height, int(y2 + pad_y))
        crop = frame.crop((left, top, right, bottom))

    scale = min(target_height / crop.height, max_width / crop.width)
    if scale > 1:
        new_size = (max(1, round(crop.width * scale)),
                    max(1, round(crop.height * scale)))
        crop = crop.resize(new_size, Image.Resampling.LANCZOS)
    if enhance:
        crop = ImageOps.autocontrast(crop, cutoff=1)
        crop = crop.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=3))
    crop.save(out_path, quality=92)
    return out_path


def sign_context_for_row(run_dir, row, out_dir, frames_subdir="frames"):
    """Everything the review sheet needs for one row.

    row: one dict from review.csv. Needs best_frame, x1, y1, x2, y2 and
    (optionally) cam_heading. Old runs have no cam_heading, so side and
    facing stay blank and the note says why.

    Returns {"crop": path or None, "side": str, "faces": str, "note": str}.
    Never raises for missing data: a blank cell is better than a crashed run.
    """
    result = {"crop": None, "side": "", "faces": "", "note": ""}
    try:
        box = tuple(float(row[k]) for k in ("x1", "y1", "x2", "y2"))
    except (KeyError, ValueError, TypeError):
        result["note"] = "no box saved - re-run needed"
        return result

    frame_path = os.path.join(run_dir, frames_subdir, row.get("best_frame", ""))
    if not os.path.isfile(frame_path):
        result["note"] = "original frame not found"
        return result

    out_path = os.path.join(out_dir, f"crop_{row.get('group_id', 'x')}.jpg")
    try:
        result["crop"] = crop_sign(frame_path, box, out_path)
    except ValueError:
        result["note"] = "bad box"
        return result

    heading_text = str(row.get("cam_heading", "") or "").strip()
    if not heading_text:
        result["note"] = "no camera heading saved - re-run needed"
        return result
    with Image.open(frame_path) as frame:
        frame_width = frame.size[0]
    guess = suggest_side_and_facing(float(heading_text), (box[0] + box[2]) / 2,
                                    frame_width)
    result.update(side=guess["side_of_street"], faces=guess["faces_traffic"],
                  note=guess["note"])
    return result