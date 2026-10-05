from ultralytics import YOLO
import os
import re
import csv
import haversine as hs
from PIL import Image
from pyproj import Geod
import json
import cv2
from GoProDataHelper import *
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from torchmetrics.text import CharErrorRate
from geo import sign_bearing, adjustCoords, calculate_bearing

def detect_and_store(src, modelName):
    model = YOLO(modelName)
    results = model.predict(source=src, conf=0.25)
    result = results[0]
    highConfSigns = []
    signTypes = []
    for box in result.boxes:
        signName = result.names[int(box.cls)]
        #path = os.path.join(os.getcwd(), f"images/{signName}_Low_Confidence")
        if box.conf.item() >= 0.4: # lowered the confidence threashold
            #track all signs
            highConfSigns.append([signName, box.conf.item(), box.xyxy.tolist()[0]])
            #save one image per sign type
            if signName not in signTypes:
                signTypes.append(signName)
                path = os.path.join(os.getcwd(), f"images/{signName}_High_Confidence")
                os.makedirs(path, exist_ok = True)
                outputPath = f"{path}/{os.path.basename(src)}"
                    #outputPath = f"{path}/{re.findall(r'streetview_frame_\d+_heading_\d+', src)[0]}.jpg"
                result.save(outputPath)
        #result.save(outputPath)
    return highConfSigns
            
        
def addToTable(filename, signName, location, url, heading, confidence):
    item = {
    'SignName' : signName,
    'ImageURL' : url,
    'Location' : location,
    'Heading': heading,
    'Confidence' : confidence
    }
    fields = ['SignName', 'ImageURL', 'Location', 'Heading', 'Confidence']
    if(os.path.exists(filename)):
        with open(file = filename, mode = "a", newline='') as f:
            writer = csv.DictWriter(f, fieldnames = fields)
            writer.writerow(item)

    else:
        with open(file = filename, mode = "x", newline='') as f:
            writer = csv.DictWriter(f, fieldnames = fields)
            writer.writeheader()
            writer.writerow(item)


def addToGISFormatTable(filename, signName, lat, long, heading):
    item = {
        'x': long,
        'y': lat,
        'z': 0.0,
        'Sign_Type': signName,
        'Sign_Suprt': "n/a",
        'Suprt_Locat': "n/a",
        'Mnt_Height': "n/a",
        'MUTCD': "n/a",
        'Stock_No': "n/a",
        'Sign_Size': "n/a",
        'Sign_Text': "n/a",
        'P_Street': "n/a",
        'Crs_Street': "n/a",
        'EoB': "n/a",
        'Side_Str': "n/a",
        'Traf_face': "n/a",
        'Dir_X_Str': "n/a",
        'Sign_Dir': "n/a",
        'Condition': "n/a",
        'Post_Type': "n/a",
        'Mnt_Surf': "n/a",
        'Cncil_Dstr': "n/a",
        
    }
    fields = item.keys()
    if(os.path.exists(filename)):
        with open(file = filename, mode = "a", newline='') as f:
            writer = csv.DictWriter(f, fieldnames = fields)
            writer.writerow(item)

    else:
        with open(file = filename, mode = "x", newline='') as f:
            writer = csv.DictWriter(f, fieldnames = fields)
            writer.writeheader()
            writer.writerow(item)


def trim_points_by_distance(points, interval):
    trimmedPoints = []
    currDist = 0
    trimmedPoints.append(points[0])
    for i in range(1, len(points)-1):
        lat1, long1 = trimmedPoints[len(trimmedPoints)-1]
        lat2, long2 = points[i]



        dist = hs.haversine((lat1, long1), (lat2, long2), hs.Unit.METERS, normalize = True)
        if(dist > interval):
            trimmedPoints.append(points[i])

    return trimmedPoints


def get_detection_depth_and_heading(model, src, boxCoords, heading, fov):
    rawSrc = newSrc = src[0:len(src)-3] + "_raw_depth.jpg" 
    boxCoords = [int(i) for i in boxCoords]
    with Image.open(src) as image:
        depth = model(image)['predicted_depth']
        depthImg = model(image)['depth']
        depthImg.save(rawSrc)
    #get depth
    sum = 0
    x1, y1, x2, y2 = boxCoords
    for row in depth[y1:y2]:
        for pixel in row[x1:x2]:
            sum += pixel
    avg_depth = sum/((x2-x1)*(y2-y1))
    
    #update heading
    boxX = (x1 + x2) / 2
    newBearing = sign_bearing(heading, boxX, depth.size(1), fov)
    return (avg_depth.item(), newBearing)

# purpose: given a box, this will zoom in and read the actaul text and figure out exactly what kinds of specific sign the object detected is
''' additions:
    - OCR can fail, and in this specifiy signs will return "" so we need to add a check for this
    so the correctly identified sign is not overwritten
'''

def ocr(boxCoords, signName, src, crop_path, ocr, ocr_candidate_signs):
    # first we need to crop the the sign from the frame
    x1, y1, x2, y2 = boxCoords
    crop_img = cv2.imread(src)[int(y1):int(y2), int(x1):int(x2)]
    # Save cropped image
    cv2.imwrite(crop_path, crop_img)
    # this is where we hand over the crop to paddleOCR and have it attempt to read the text
    text_prediction = ocr.predict(crop_path)
    words = []
    # only one result
    for res in text_prediction: 
        res.save_to_json("images/temp/jsons/sign_name_data.json")
        with open("images/temp/jsons/sign_name_data.json", 'r', encoding='cp850') as f:
            j = json.load(f)
            # it may be worth pairing words with their confidence level
            words = j['rec_texts'] # all the successful reads together
    best_match, cers = specifySigns(signName, words, ocr_candidate_signs)
    # If OCR found nothing or nothing matched, keep the detector's label
    return best_match if best_match else signName

def load_excel():
    # Define the scope of API
    print("Loading sign information from Google Sheet")
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    # Authenticate with credentials
    credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(credentials)

    # Open the Google Sheet
    MASTER_SHEET_INDEX = 0
    sheet = client.open('Tracker - Merged Master Sign Catalog ').get_worksheet(MASTER_SHEET_INDEX)
    return sheet.get_all_records() # return all unique signs in the Google sheet

# have a list of ocr candidate
'''
purpose:
    - given a list of words from OCR, figure out which offical sign it most closely matches from the catalog


additions:
    - currently the lowest_cer becomes "" if the first option the checks happens to be empty or broken
'''
def specifySigns(baseSign, words, ocr_candidate_signs):
    cer = CharErrorRate() # CER --> lower the CER the closer two words are
    cers = {}
    if (len(words) == 0): return "", {}
    prediction = " ".join(words).capitalize() # turn list into one string
    # for each sign type
    for ocr_candidate_sign in ocr_candidate_signs:
        if (ocr_candidate_sign["Bounding box name"] == baseSign):
            ocr_desc = " ".join(ocr_candidate_sign["OCR Desc"].split('\n')).capitalize()
            # calculate CER (without normalizing to len(ocr_desc))
            cers[ocr_desc] = cer(prediction, ocr_desc).item()
    best_match = min(cers, key=cers.get) if cers else ""
    return best_match, cers

def is_ocr_canditate(unique_sign):
    return unique_sign["OCR candidate?"] == "y"

def GoProProcessing(input_mp4, outdir, interval, interp_gap, nearest_gap):

    print("Output folder:", Path(outdir))
    frames = extract_frames_every_n_seconds(input_mp4, outdir, interval)
    print(f"Extracted {len(frames)} frames")
    exiftool_bin = exiftool_cmd()
    if not exiftool_bin:
        print("[WARN] exiftool not found. Frames will be left without GPS EXIF.")
        samples = []; static_gps = None
    else:
        print("Using exiftool:", exiftool_bin)
        samples    = run_exiftool_timed_gps(input_mp4, exiftool_bin)
        static_gps = run_exiftool_static_gps(input_mp4, exiftool_bin)
        print(f"Timed GPS samples: {len(samples)} | Static GPS available: {bool(static_gps)}")

    wrote = 0
    for jpg_path, ts in frames:
        latlon = None
        if samples:
            latlon = interpolate_gps(ts, samples, per_side_gap=interp_gap) or nearest_gps(ts, samples, max_gap=nearest_gap)
        if latlon is None and static_gps is not None:
            latlon = static_gps
            print("no timed gps")
        if latlon:
            write_gps_exif(jpg_path, latlon[0], latlon[1])
            wrote += 1

    print(f"GPS EXIF written on {wrote}/{len(frames)} frames.")
    print("Done. First few files:")
    for p, _t in frames[:5]:
        print("  ", p)



def GoProFrames(input_mp4, outdir, interval):
    exiftool_bin = exiftool_cmd()

    frames = extract_frames_every_n_seconds(input_mp4, outdir, interval)
    gpsData = get_gopro_timed_gps(input_mp4, exiftool_bin)

    pairedData = []
    frameNum = 0
    timer = 0
    previous = float(gpsData[0][1].split(':')[2])
    for data in gpsData:
        time = float(data[1].split(':')[2])
        if(previous >= 59.0):
            timer+= (60.0-previous) + time
        else:
            timer+=time-previous
        
        if(timer >= interval):
            timer -= interval

            pairedData.append([frames[frameNum][0], data[2], data[3], data[4]])
            frameNum+=1
        previous = time

    return pairedData



