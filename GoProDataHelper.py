# - Uses exiftool -ee3 (GPMF), filters bad fixes (GPSFix>=2), interpolates, and falls back to static GPS
# - Set your paths in the "USER SETTINGS" section below

import os, math, shutil, subprocess
from pathlib import Path
from typing import List, Tuple, Optional
from bisect import bisect_left
from datetime import datetime, timezone


import cv2
from PIL import Image
import piexif

# ------------------------ USER SETTINGS (EDIT) ------------------------ #
#input_mp4   = r"Z:\_Projects\Asset_Recognition\Yolo_Video\Videos from Nick\GH010296.MP4"
#outdir      = r"Z:\_Projects\Asset_Recognition\Yolo_Video\Videos from Nick\GH010296 3"
#interval    = 5.0      # seconds between frames
#interp_gap  = 15.0     # per-side seconds for interpolation
#nearest_gap = 10.0     # max seconds for nearest fallback
# EXIFTOOL    = "exiftool-13.40_64/exiftool.exe" 
EXIFTOOL    = "/usr/local/bin/exiftool.exe"  # set to None if exiftool is on PATH
HFOV_DEG = 87.0 # horizontal FOV, HERO10 Black, Linear, HyperSmooth High (GoPro FOV table)
MAX_GPS_GAP_S = 3.0 # in case of gps signla being lost 
# --------------------------------------------------------------------- #

def exiftool_cmd() -> Optional[str]:
    """Resolve a usable exiftool path or return None if not found."""
    if EXIFTOOL and os.path.exists(EXIFTOOL):
        return EXIFTOOL
    return shutil.which("exiftool")


# Use this to grab gps data, regardless of other stuff
# Map to each image based on time stamp
# pair and pass to algorithm

# ---------- GPS extraction (GoPro-aware) ----------
def run_exiftool_timed_gps(mp4_path: str, exiftool_bin: str) -> List[Tuple[float, float, float]]:
    """
    Use -ee3 to pull GoPro GPMF timed GPS + GPSFix.
    Returns [(time_s, lat, lon)] filtered to good fixes (GPSFix >= 2).
    """
    cmd = [
        exiftool_bin, "-ee3", "-api", "largefilesupport=1", "-n",
        "-p", "$GPSDateTime $GPSLatitude $GPSLongitude $Doc1:GPSHPositioningError",
        mp4_path
    ]
    print("pre statement")
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError:
        print("ERROR OR SMTH")
        return []
    samples: List[Tuple[float, float, float]] = []
    print("pre loop")
    print(out)
    for line in out.splitlines():
        parts = line.strip().split()
        #print(parts)
        if len(parts) >= 4:
            try:
                t   = float(parts[0]); lat = float(parts[1]); lon = float(parts[2])
                fix = int(float(parts[3]))  # sometimes "3.00"
                if not (math.isnan(lat) or math.isnan(lon)) and fix >= 1:
                    samples.append((t, lat, lon))
            except Exception:
                pass
    samples.sort(key=lambda x: x[0])
    return samples

def run_exiftool_static_gps(mp4_path: str, exiftool_bin: str) -> Optional[Tuple[float, float]]:
    """Try QuickTime:GPSCoordinates (numeric) then ISO6709; return (lat, lon) or None."""
    # QuickTime:GPSCoordinates
    try:
        out = subprocess.check_output(
            [exiftool_bin, "-s", "-s", "-s", "-n", "-QuickTime:GPSCoordinates", mp4_path],
            stderr=subprocess.STDOUT, text=True
        ).strip()
        if out:
            parts = out.split()
            if len(parts) >= 2:
                return float(parts[0]), float(parts[1])
    except Exception:
        pass
    # ISO6709 (+lat-lon[/alt])
    try:
        out = subprocess.check_output(
            [exiftool_bin, "-s", "-s", "-s", "-com.apple.quicktime.location.ISO6709", mp4_path],
            stderr=subprocess.STDOUT, text=True
        ).strip()
        if out:
            iso = out[:-1] if out.endswith("/") else out
            # split into lat | lon by second sign
            idx = next((i for i in range(1, len(iso)) if iso[i] in "+-"), None)
            if idx is not None:
                lat = float(iso[:idx])
                rest = iso[idx:]
                idx2 = next((j for j in range(1, len(rest)) if rest[j] in "+-"), None)
                lon = float(rest if idx2 is None else rest[:idx2])
                return lat, lon
    except Exception:
        pass
    return None

def interpolate_gps(t: float, samples: List[Tuple[float, float, float]], per_side_gap: float = 15.0) -> Optional[Tuple[float, float]]:
    """Linear interpolation between samples around t; falls back to one-sided carry."""
    if not samples:
        return None
    times = [s[0] for s in samples]
    i = bisect_left(times, t)
    prev = samples[i-1] if i > 0 else None
    nxt  = samples[i]   if i < len(samples) else None
    if prev and nxt and (t - prev[0] <= per_side_gap) and (nxt[0] - t <= per_side_gap) and (nxt[0] > prev[0]):
        frac = (t - prev[0]) / (nxt[0] - prev[0])
        lat = prev[1] + frac * (nxt[1] - prev[1])
        lon = prev[2] + frac * (nxt[2] - prev[2])
        return (lat, lon)
    if prev and (t - prev[0] <= per_side_gap):
        return (prev[1], prev[2])
    if nxt and (nxt[0] - t <= per_side_gap):
        return (nxt[1], nxt[2])
    return None

def nearest_gps(t: float, samples: List[Tuple[float, float, float]], max_gap: float = 10.0) -> Optional[Tuple[float, float]]:
    """Nearest sample if within max_gap seconds."""
    if not samples:
        return None
    best = None; best_dt = float("inf")
    for ts, lat, lon in samples:
        dt = abs(ts - t)
        if dt < best_dt:
            best_dt = dt; best = (lat, lon)
    return best if best_dt <= max_gap else None

# ---------- EXIF GPS writing ----------
def _to_rational_deg(value: float):
    """Decimal degrees -> EXIF rationals ((deg, min, sec) as (num, den))."""
    abs_val = abs(value)
    deg = int(abs_val)
    minutes_float = (abs_val - deg) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    den = 1_000_000
    return ((deg * den, den), (minutes * den, den), (int(round(seconds * den)), den))


def write_gps_exif(jpg_path: str, lat: float, lon: float):
    """Write GPS EXIF to a JPEG."""
    try:
        img = Image.open(jpg_path)
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
        try:
            existing = img.info.get("exif")
            if existing:
                exif_dict = piexif.load(existing)
        except Exception:
            pass
        gps_ifd = exif_dict.get("GPS", {})
        gps_ifd[piexif.GPSIFD.GPSLatitudeRef]  = b"N" if lat >= 0 else b"S"
        gps_ifd[piexif.GPSIFD.GPSLongitudeRef] = b"E" if lon >= 0 else b"W"
        gps_ifd[piexif.GPSIFD.GPSLatitude]     = _to_rational_deg(lat)
        gps_ifd[piexif.GPSIFD.GPSLongitude]    = _to_rational_deg(lon)
        gps_ifd[piexif.GPSIFD.GPSVersionID]    = (2, 3, 0, 0)
        exif_dict["GPS"] = gps_ifd
        exif_bytes = piexif.dump(exif_dict)
        img.save(jpg_path, "jpeg", exif=exif_bytes)
        img.close()
    except Exception as e:
        print(f"[WARN] EXIF write failed for {jpg_path}: {e}")

# ---------- Frame extraction ----------
def extract_frames_every_n_seconds(mp4_path: str, out_dir: str, interval: float = 5.0) -> List[Tuple[str, float]]:
    """Extract frames at 0, N, 2N, ... seconds. Returns [(jpg_path, t_seconds)]."""
    cap = cv2.VideoCapture(mp4_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {mp4_path}")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    outputs: List[Tuple[str, float]] = []
    idx = 0
    while True:
        t = idx * float(interval)
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, frame = cap.read()
        if not ok:
            break
        jpg_path = os.path.join(out_dir, f"frame_{int(round(t)):06d}s.jpg")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        Image.fromarray(rgb).save(jpg_path, "JPEG", quality=95)
        outputs.append((jpg_path, t))
        idx += 1
    cap.release()
    return outputs

# ============================ RUN THE PIPELINE ============================ #


def exiftool_cmd() -> Optional[str]:
    """Resolve a usable exiftool path or return None if not found."""
    if EXIFTOOL and os.path.exists(EXIFTOOL):
        return EXIFTOOL
    return shutil.which("exiftool")


# Use this to grab gps data, regardless of other stuff
# Map to each image based on time stamp
# pair and pass to algorithm

# ---------- GPS extraction (GoPro-aware) ----------
def gps_time_to_seconds(date_str, time_str):
    """Convert GPSDateTime string to seconds since epoch. ex output: 2025:10:14 00:29:51.599"""
    time_str = time_str.rstrip("Z")  # Remove trailing 'Z' (not always there)
    # format YYYY:MM:DD HH:MM:SS[.fff]
    fmt = "%Y:%m:%d %H:%M:%S.%f" if "." in time_str else "%Y:%m:%d %H:%M:%S"
    dt = datetime.strptime(f"{date_str} {time_str}", fmt)
    return dt.replace(tzinfo=timezone.utc).timestamp()

def get_gopro_timed_gps(mp4_path, exiftool_bin):
    """ Return a list that is sorted of (time_in_Seconds, lat, lon) tuples from the GoPro GPMF data. """
    # first make the terminal commd to extract the raw telemetry from the video 
    cmd = [exiftool_bin, "-ee3", "-api", "largefilesupport=1", "-n",
           "-p", "$SampleTime $GPSDateTime $GPSLatitude $GPSLongitude", mp4_path]

    # now we have gone through the full video and extracted all the metadata embeeded in it.
    # we can run it
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running exiftool: {result.stderr}")

    # create a list to hold the gps data
    samples = []

    # start parsing the output line by line
    for line in result.stdout.splitlines():
        parts = line.strip().split() # get the individual tokens 

        # a vild line will look like: [SampleTime, Date, Time, Latitude, Longitude]
        if len(parts) != 5:
            continue # skip invalid lines  

        try:
            video_t = float(parts[0])
            utc_t = gps_time_to_seconds(parts[1], parts[2])
            lat = float(parts[3])
            lon = float(parts[4])
        except ValueError:
            continue  # skip lines with conversion errors

        # we now can filter out the invalid lines
        # GoPro defaults to (0.0, 0.0) before satellite lock is acquired ("Null Island")
        if lat == 0.0 and lon == 0.0:
            continue  # skip invalid GPS coordinates

        # add the valid gps data to the list
        samples.append((video_t, utc_t, lat, lon))

    # now sort and check that all the coordinates are ordered chronologically by timestamp
    samples.sort(key=lambda x: x[0])

    if not samples:
        # print("No valid GPS data found in the GoPro video.")
        raise RuntimeError("No valid GPS data found in the GoPro video.")

    return samples
        