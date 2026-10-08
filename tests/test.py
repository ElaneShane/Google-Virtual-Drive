import drive
import helper
from load_excel_and_test_ocr import load_excel

with open('secrets.txt') as f:
    API_KEY = f.readline().strip('\n')

#select start and finish locations using google maps addresses 
origin = "100 Main St 10th Floor, Los Angeles, CA 90012"
destination = "4884 Eagle Rock Blvd, Los Angeles, CA 90041"

# load the signs
unique_signs = list(filter(helper.is_ocr_canditate, load_excel()))
print("Retrieved OCR candidate sign information")

#Use Routes API
#drive.drive_route(origin, destination, API_KEY, minStep=30, fov = 90, datafile='tables/drive2.csv', ocr_candidate_signs=unique_signs)

#Use CSV Coordinates
#drive.csv_drive("GrandAv.csv", API_KEY, pitchAngle=5, fov=90, datafile='tables/drive1.csv')

input_mp4   = "/Users/serenali/ahahahhaahaha/ladot/Google-Virtual-Drive/video/GX040300.MP4"
outdir      = "/Users/serenali/ahahahhaahaha/ladot/Google-Virtual-Drive/video"
interval    = 5      # seconds between frames
interp_gap  = 15.0     # per-side seconds for interpolation
nearest_gap = 10.0     # max seconds for nearest fallback

#helper.GoProProcessing(input_mp4, outdir, interval, interp_gap, nearest_gap)
#helper.GoProFrames(input_mp4, outdir, interval)    
drive.drive_gopro(input_mp4, interval, datafile='tables/drive1.csv', ocr_candidate_signs=unique_signs)
#helper.get_gopro_timed_gps(input_mp4, helper.exiftool_cmd())