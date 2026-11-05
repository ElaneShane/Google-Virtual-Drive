import os
import re
import xml.etree.ElementTree as ET
from urllib.parse import unquote


def load_class_names(config_path):
    """Class names from a Label Studio XML config, in file order (position = class number)."""
    root = ET.parse(config_path).getroot()
    block = root.find(".//RectangleLabels")
    if block is None:
        raise ValueError("No <RectangleLabels> block found in the config")
    names = [lab.get("value") for lab in block.findall("Label")]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate class names in the config")
    return names


def rect_to_yolo(value):
    """Label Studio box (percent, top-left corner) -> (x_center, y_center, w, h), each 0 to 1."""
    x1 = max(0.0, value["x"])
    y1 = max(0.0, value["y"])
    x2 = min(100.0, value["x"] + value["width"])
    y2 = min(100.0, value["y"] + value["height"])
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Empty box after clamping: {value}")
    return ((x1 + x2) / 200, (y1 + y2) / 200, (x2 - x1) / 100, (y2 - y1) / 100)


def pick_annotation(task):
    """The last annotation that was not cancelled, or None."""
    anns = [a for a in task.get("annotations", []) if not a.get("was_cancelled")]
    return anns[-1] if anns else None


def parse_task(task, class_ids):
    """One exported task -> (yolo_lines, condition, problems).
    class_ids maps class name -> number. An empty yolo_lines list is a valid 'no signs' frame."""
    ann = pick_annotation(task)
    if ann is None:
        raise ValueError("task has no usable annotation")
    lines, problems, condition = [], [], ""
    for r in ann.get("result", []):
        kind = r.get("type")
        v = r.get("value", {})
        if kind == "choices":
            choices = v.get("choices", [])
            if choices:
                condition = choices[0]
        elif kind == "rectanglelabels":
            labels = v.get("rectanglelabels", [])
            if len(labels) != 1:
                problems.append(f"box with {len(labels)} labels")
                continue
            name = labels[0]
            if name not in class_ids:
                problems.append(f"unknown label: {name!r}")
                continue
            if v.get("rotation") not in (None, 0, 0.0):
                problems.append(f"rotated box on {name!r}")
                continue
            try:
                xc, yc, w, h = rect_to_yolo(v)
            except (KeyError, ValueError) as e:
                problems.append(f"bad box on {name!r}: {e}")
                continue
            lines.append(f"{class_ids[name]} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")
        else:
            problems.append(f"unexpected shape type: {kind!r}")
    return lines, condition, problems


def ls_image_path(image_field, media_root):
    """'/data/upload/2/abc-frame_0001.jpg' -> '<media_root>/upload/2/abc-frame_0001.jpg'."""
    m = re.match(r"^/data/upload/(\d+)/(.+)$", image_field)
    if not m:
        raise ValueError(f"Not an uploaded-image path: {image_field!r}")
    return os.path.join(media_root, "upload", m.group(1), unquote(m.group(2)))


def local_files_path(image_field, local_root):
    """'/data/local-files/?d=<path>' -> real file path.
    <path> is either relative to local_root or a full path with its leading '/' removed."""
    m = re.match(r"^/data/local-files/\?d=(.+)$", image_field)
    if not m:
        raise ValueError(f"Not a local-files path: {image_field!r}")
    d = unquote(m.group(1))
    if d.startswith("/"):
        return d
    rel = os.path.join(local_root, d)
    return rel if os.path.exists(rel) else "/" + d


def resolve_image(image_field, media_root, local_root):
    """Uploaded copy or local file, whichever the export points at."""
    if image_field.startswith("/data/upload/"):
        return ls_image_path(image_field, media_root)
    return local_files_path(image_field, local_root)