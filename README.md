# Virtual Drive

Finds street signs in video from city trucks, groups repeat sightings of the
same sign, and helps a person check them in a review spreadsheet. The checked
rows become a CSV with a latitude and longitude for each sign, for the GIS team.

This is an in-progress internship project. The sign detector is an early
version, and its accuracy is still being measured (see Status below). The model
proposes and a person confirms: nothing is meant to go into GIS without a
person checking it first.

## What it does

1. Cuts a frame from the video every N seconds.
2. Reads the camera's GPS track, removes bad GPS points, and works out which
   direction the truck was heading at each frame.
3. Runs YOLO sign detection on each frame.
4. Estimates each sign's distance (depth model) and compass bearing, then
   places it on the map.
5. Groups sightings of the same sign across frames, and sorts them into
   "likely" and "review" tiers.
6. Builds a review spreadsheet (`review.xlsx`) with a picture, drop-downs, a
   map link and a sign-catalog match for each group.
7. After a person reviews the sheet, writes a CSV for GIS with only the checked
   signs (`gis_export.csv`), plus a second file listing what was left out and why.

A second, older mode builds training pictures from Google Street View
(see "Street View mode" below).

## Setup

1. Create a Python virtual environment (developed on Python 3.12) and run:
   `pip install -r requirements.txt`
2. Install ExifTool (https://exiftool.org) so the `exiftool` command works in
   your terminal. It reads GPS and camera settings from GoPro video.
3. Put YOLO model files (.pt) in a folder. Model files are not in this repo.
   By default the code uses every .pt file directly inside `models/`.

## Step 1: Run it on a GoPro clip

    python run_gopro_tests.py "path/to/clip.MP4" [models_dir] [imgsz] [interval]

- `models_dir` is optional. Use it to run one model by itself,
  for example `models/models_run_g`.
- `imgsz` is optional. It is the size YOLO shrinks each frame to.
  Bigger sizes can find smaller signs but are slower.
- `interval` is optional. Seconds between frames (default 2).

Example:

    python run_gopro_tests.py "$HOME/clips/clip.MP4" models/models_run_g 1280 2

Each run saves to its own folder, so runs never overwrite each other:

    runs/<clip>_<date>_<time>/
        frames/              cut frames and gps_diagnostic.csv
        detections/          pictures with boxes drawn
        crops/               sign crops used for text reading
        signs.csv            output in the GIS field format
        debug_detections.csv every detection with confidence and bearing

## Step 2: Group sightings and build the review sheet

    RUN=$(ls -dt runs/* | head -1)       # the newest run folder
    python make_review.py $RUN 2         # 2 = the interval you used in step 1
    python make_review_xlsx.py $RUN

`make_review.py` (uses `group_detections.py`) joins sightings of the same sign
and writes `review.csv`. The rules and thresholds are at the top of
`group_detections.py`. All of them are starting guesses, tuned on a few signs:

- Same class name, never twice in one frame, within a few frame intervals.
- If both sightings have a trusted position (sign closer than 45 m), they must
  be near each other.
- **likely**: seen in 2 or more frames with best confidence of at least 0.4.
- **review**: everything else with best confidence of at least 0.25.
- Under 0.25 is dropped.

`make_review_xlsx.py` writes `review.xlsx` in the run folder. For each group it
shows the best picture, the model's name and confidence, a **Decision**
drop-down (correct, wrong name, not a sign, can't tell; blank means not
reviewed yet), a **Correct name** drop-down of the model's classes, a Google
Maps pin link (or "needs location"), and the sign-catalog match. A "How to
review" tab explains each column.

## Step 3: Sign catalog lookup

Stock numbers and MUTCD codes come from two files that are not in this repo:
`class_map_v1.csv` (maps detector class names to catalog stock numbers) and the
LA Standard Sign Catalog spreadsheet. Build the lookup once:

    python make_lookup.py

It expects both files in `~/ladot-virtual-drive/` (the catalog as
`LA_Standard_Sign_Catalog.xlsx`, the class map in `clips/`) and the class list
in `uncomitted/label_config_G.xml`. It writes `sign_lookup.csv` there.

A stock number is filled in only when the class has exactly one stock number in
the class map. Classes with a few versions list them as candidates. Classes
with many versions, or with no match, are left blank for GIS to fill in.
Classes listed in `HOLD` in `sign_lookup.py` are blank on purpose until
someone checks them.

## Step 4: Export the reviewed sheet for GIS

Review `review.xlsx` (open it in Google Sheets), download it as .xlsx, and put
it back in the run folder as `review.xlsx`. Then:

    python export_reviewed.py $RUN

This writes two files in the run folder:

- `gis_export.csv`: rows marked correct or wrong name that have a location.
  For wrong-name rows the corrected name is used to look up the stock number.
- `not_exported.csv`: everything else, with a `reason` (not a sign, can't tell,
  not reviewed, needs location, and so on).

## Run it in Google Colab

`notebooks/sign_detection.ipynb` runs steps 1 to 4 in Colab, using a shared
Drive folder for the model files, lookup, catalog, clips and results. The notebook
has instructions at the top. It has had limited testing so far.

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

`signs.csv` (step 1) uses the GIS team's field names. The pipeline fills x, y
and sign type there. `gis_export.csv` (step 4) is the reviewed version, with
lat, lon, stock number, MUTCD code, confidence and the review decision. Other
GIS fields (text, arrow, streets, condition) are not filled in.

## Tests

    python -m pytest -q

## Street View mode (older)

`csv_drive` and `drive_route` in `drive.py` build pictures from Google Street
View. They need an API key in `secrets.txt` and, for Google Sheets,
service-account credentials in `credentials.json`. Keep both files out of git.
These modes have not been run since the GoPro work began.

## Status

- Sign detection accuracy is low and is measured on a small test set. Treat
  every detection as a proposal for a person to check.
- Sign locations have not been checked against real positions. They are
  estimates from GPS plus depth and can be off by several meters.
- Depth estimates have not been checked against measured distances.
- Grouping and tier thresholds are starting guesses.
- The export has not been checked against what the GIS layer expects
  (field names, coordinate system).

## Not in this repo

Sign images, trained model files, the sign catalog, the class map, the sign
lookup, city video and exported GIS data are not included.