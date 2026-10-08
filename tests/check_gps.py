import os
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from GoProDataHelper import exiftool_cmd, get_gopro_timed_gps

clip = os.path.expanduser("~/ladot-virtual-drive/clips/GH010296.MP4")
exe = exiftool_cmd()
print("exiftool found at:", exe)
rows = get_gopro_timed_gps(clip, exe)
print(len(rows), "usable GPS rows")
print(rows[:3])
print("last:", rows[-1:] )