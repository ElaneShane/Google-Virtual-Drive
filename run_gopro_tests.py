import os
import sys
from datetime import datetime
import drive

#  Usage: python run_gopro_tests.py path/to/clip.MP4"
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_gopro_tests.py path/to/clip.MP4")
        sys.exit(1)

    clip = os.path.expanduser(sys.argv[1])        # the path you typed after the script name
    name = os.path.splitext(os.path.basename(clip))[0].replace(" ", "_")

    # one new folder per run: clip name + date + time, so runs never overwrite each other
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_dir = os.path.join("runs", f"{name}_{stamp}")
    os.makedirs(run_dir, exist_ok=True)

    datafile = os.path.join(run_dir, "signs.csv")
    drive.drive_gopro(clip, 12, datafile=datafile, ocr_candidate_signs=[], run_dir=run_dir)
    print(f"Everything from this run is in: {run_dir}")