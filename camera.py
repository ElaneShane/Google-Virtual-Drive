import csv
import json
import os
import subprocess



# Maps a known camera configuration to its horizontal
# field of view (HFOV), measured in degrees.
#
# Each key contains:
#   1. Camera model
#   2. Lens / field-of-view setting
#   3. Electronic image stabilization setting
#
# These strings must match the values returned by ExifTool.
# The values are based on the GoPro FOV specifications.

# IMPORTANT:
# Only add combinations whose FOV has been verified.


HFOV_TABLE = {
    ("HERO10 Black", "Linear", "HS High"): 87.0,

    # Assumption: HyperSmooth is On or High.
    # Both are listed as 109 degrees for this configuration.
    # Boost would be 92 degrees, and Off would be 118 degrees.
    # This particular assumption still needs verification.
    ("HERO9 Black", "Wide", "HS EIS"): 109.0,
}


def lookup_hfov(model, lens, stabilization):
    """
    Return the horizontal field of view for a known
    camera model, lens setting, and stabilization setting.
    """

    key = (model, lens, stabilization) # the three settings taken from the meta data
    if key not in HFOV_TABLE:
        raise ValueError(f"Unknown camera setup {key}. Add it to HFOV_TABLE "
            "in camera.py using GoPro's FOV datasheet. Not guessing."
        )

    return HFOV_TABLE[key] # the verifited HFOV in degrees


def read_camera_settings(mp4_path, exiftool_bin="exiftool"):
    """
        Read camera settings embedded in an MP4 file.

        Returns:
            (model, lens, stabilization)"""
    result = subprocess.run(
        [
            exiftool_bin,
            "-j",
            "-Model",
            "-FieldOfView",
            "-ElectronicImageStabilization",
            mp4_path,
        ],
        capture_output=True,
        text=True,
    )

    # exiftool will return like json 
    try:
        info = json.loads(result.stdout)[0]
    except (json.JSONDecodeError, IndexError):
        info = {}
    # .get() returns None when a tag is missing.
    return (
        info.get("Model"),
        info.get("FieldOfView"),
        info.get("ElectronicImageStabilization"),
    )

def hfov_for_clip(mp4_path, exiftool_bin="exiftool"):
    """ Get the horizontail field of view for a video clip"""

    model, lens, stab = read_camera_settings(
        mp4_path, exiftool_bin
    )

    # match it against the known configurations
    return lookup_hfov(model, lens, stab)


# Default CSV file containing the camera direction
# for each video clip.
CLIP_SETTINGS_FILE = "clip_settings.csv"

def yaw_for_clip(mp4_path, settings_file=CLIP_SETTINGS_FILE):
    """ Return (yaw_degrees, status) for a video clip.

    The CSV must contain the clip's filename, yaw angle,
    and status. If the clip is missing or its direction
    is unknown, stop instead of inventing a direction."""

    # first get the filename
    name = os.path.basename(mp4_path)
    if not os.path.exists(settings_file):
        raise FileNotFoundError(
            f"{settings_file} not found. It lists the camera "
            "direction for every clip."
        )

    # Open the CSV and read it as rows of named columns.
    with open(settings_file, newline="") as f:
        for row in csv.DictReader(f):
            # match the clip filename
            if row["clip"].strip() == name:
                # don't calculate locations when the yaw is unknown or has not been filled in
                if (
                    row["status"].strip() == "unknown"
                    or not row["yaw_deg"].strip()
                ):
                    raise ValueError(
                        f"Camera direction for {name} is unknown, "
                        "so sign locations can't be computed. "
                        f"Fill in yaw_deg in {settings_file}."
                    )
                # Convert the yaw to a number and normalize it
                # to the range [0, 360).
                # Return both the normalized angle and its status.
                return (
                    float(row["yaw_deg"]) % 360,
                    row["status"].strip(),
                )

    # If we reach here, the file exists but has no matching row.
    # Require an explicit entry for every video clip.
    raise ValueError(
        f"{name} is not in {settings_file}. "
        f"Add a line: {name},<yaw_deg>,assumed"
    )

            
