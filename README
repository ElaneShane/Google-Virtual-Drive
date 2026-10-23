# Virtual Drive

Finds street signs in video from city trucks and writes them to a CSV in the
GIS team's field format, with an estimated location for each sign.

This is an in-progress internship project. The sign detector is an early
version, and its accuracy has not been measured yet (see Status below).

## What it does

1. Cuts a frame from the video every N seconds.
2. Reads the camera's GPS track, removes bad GPS points, and works out which
   direction the truck was heading at each frame.
3. Runs YOLO sign detection on each frame.
4. Estimates each sign's distance (depth model) and compass bearing, then
   places it on the map.
5. Writes a CSV of signs, plus a debug file and annotated pictures.

A second, older mode builds training pictures from Google Street View
(see "Street View mode" below).

## Setup

1. Create a Python virtual environment (developed on Python 3.12) and run:
   `pip install -r requirements.txt`
2. Install ExifTool (https://exiftool.org) so the `exiftool` command works in
   your terminal. It reads GPS and camera settings from GoPro video.
3. Put YOLO model files (.pt) in a folder. Model files are not in this repo.
   By default the code uses every .pt file directly inside `models/`.

## Run it on a GoPro clip

    python run_gopro_tests.py "path/to/clip.MP4" [models_dir] [imgsz]

- `models_dir` is optional. Use it to run one model by itself,
  for example `models/models_v2`.
- `imgsz` is optional. It is the size YOLO shrinks each frame to.
  Bigger sizes can find smaller signs but are slower.

Example:

    python run_gopro_tests.py "$HOME/clips/clip.MP4" models/models_v2 1280

Each run saves to its own folder, so runs never overwrite each other:

    runs/<clip>_<date>_<time>/
        frames/              cut frames and gps_diagnostic.csv
        detections/          pictures with boxes drawn
        crops/               sign crops used for text reading
        signs.csv            output in the GIS field format
        debug_detections.csv every detection with confidence and bearing

## Camera settings

The field of view depends on the camera model, lens setting and
stabilization. `camera.py` reads these from each video and looks up the value
in `clip_settings.csv`. If it finds a combination it does not know, it stops
with a message instead of guessing. Add new cameras to that file only after
checking GoPro's official field-of-view table.

## GPS handling

GoPro GPS is unreliable when the camera has no satellite lock. The pipeline
removes points with no lock, and points that moved far more than the camera's
own speed says they should have. Removed points are listed in
`gps_diagnostic.csv`. A frame with no trusted GPS is still checked for signs,
but its location is left blank for a person to review.
The thresholds in `gps_quality.py` are placeholders based on two clips.

## Output format

`signs.csv` uses the GIS team's field names. The pipeline fills x, y and
sign type. Other fields (stock number, MUTCD code, text, arrow, streets,
condition) are left blank for now.

## Tests

    python -m pytest -q

## Street View mode (older)

`csv_drive` and `drive_route` in `drive.py` build pictures from Google Street
View. They need an API key in `secrets.txt` and, for Google Sheets,
service-account credentials in `credentials.json`. Keep both files out of git.
These modes have not been run since the GoPro work began.

## Status

- Sign detection accuracy has not been measured yet. A labeled set of truck
  video frames is being built to measure it.
- Sign locations have not been checked against real positions.
- Depth estimates have not been checked against measured distances.

## Not in this repo

Sign images, trained model files, the sign catalog, city video and exported
GIS data are not included.