import polyline
import requests
import os
import csv
import time
from datetime import datetime
from google.maps import routing_v2
import json
from transformers import pipeline
from helper import *
from paddleocr import PaddleOCR
from geo import update_heading
from ultralytics import YOLO
ocrSigns = ["Tow Away Signs Letters", "Hourly Parking Sign"]


def csv_drive(filename, API_KEY, fov = 90, pitchAngle=0, datafile = None, ocr_candidate_signs = []):
    data_list = []
    if(datafile != None):
        os.makedirs(f'tables', exist_ok = True)


    with open(filename, 'r', newline='') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            data_list.append([row[1], row[2]])
    data_list.pop(0)

    outputFolder = "images/raw"
    os.makedirs(outputFolder, exist_ok = True)
    #max image size is 640x640
    imageSize = "640x640"
    i=1

    #load Depth Anything v2 Model
    depthModel = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Metric-Outdoor-Small-hf")

    #load paddleOCR model
    ocrModel = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False)
    
    #get pictures from the longitude latitude points using streetview api and save them
    for (log, lat) in data_list:
        locationStr = f"{lat},{log}"
        url = f"https://maps.googleapis.com/maps/api/streetview/metadata?location={locationStr}&key={API_KEY}"
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            details = json.loads(response.content)
            locationStr = f"{details["location"]["lat"]},{details["location"]["lng"]}"
            log = details["location"]["lng"]
            lat = details["location"]["lat"]
        except Exception as e:
            print(e)        

        for headingMult in range(360//fov):
            url = f"https://maps.googleapis.com/maps/api/streetview?size={imageSize}&location={locationStr}&fov={fov}&pitch={pitchAngle}&key={API_KEY}&heading={fov*headingMult}&scale=2&radius=10"
            try:
                response = requests.get(url, stream=True)
                response.raise_for_status()
                imagePath = os.path.join(outputFolder, f"streetview_frame_{i}_heading_{fov*headingMult}.jpg")
                with open(imagePath, 'wb') as outfile:
                    outfile.write(response.content)
                for model in os.listdir(os.path.join(os.getcwd(), "models")):
                    found = detect_and_store(f"images/raw/streetview_frame_{i}_heading_{fov*headingMult}.jpg", f"models/{model}", locationStr)
                    if(datafile != None):   
                        for sign, conf, shape in found:
                            strippedurl = f"https://maps.googleapis.com/maps/api/streetview?size={imageSize}&location={locationStr}&fov={fov}&pitch={pitchAngle}&key=#####&heading={fov*headingMult}&scale=2&radius=10&source=outdoor"
                            depth, newBearing = get_detection_depth_and_heading(depthModel, imagePath, shape, fov*headingMult, fov)
                            sign_lat, sign_lon = adjustCoords(lat, log, newBearing, depth)
                            if sign in ocrSigns:
                                sign = ocr(shape, sign, f"images/raw/streetview_frame_{i}_heading_{fov*headingMult}.jpg",
                                        f"images/temp/cropped/crop_frame_{i}_heading_{fov*headingMult}_sign_{sign}.jpg", ocrModel, ocr_candidate_signs)
                            addToGISFormatTable(datafile, sign, sign_lat, sign_lon, newBearing)
            except Exception as e:
                print(e)
        i+=1



# google street view 
def drive_route(origin, destination, API_KEY, minStep = 20, fov = 90, pitchAngle = 10, datafile = None, ocr_candidate_signs = []):

    if(datafile != None):
        os.makedirs(f'tables', exist_ok = True)

    #find directions and convert to polyline and then longitude, latitude pairs
    client = routing_v2.RoutesClient(
        client_options={"api_key" : API_KEY},

    )
    route_origin = routing_v2.Waypoint(address = origin)
    route_destination = routing_v2.Waypoint(address = destination)
    request = routing_v2.ComputeRoutesRequest(
        origin = route_origin, 
        destination = route_destination,    
        route_modifiers = routing_v2.RouteModifiers(avoid_highways = True)
        )
    
    
    route = client.compute_routes(request= request, metadata=[("x-goog-fieldmask", "routes.polyline.encodedPolyline")])
    route = route.routes[0]
    route_polyline = route.polyline.encoded_polyline
    route_points = polyline.decode(route_polyline)
    #prepare images folder

    outputFolder = "images/raw"
    croppedImageFolder = "images/temp/cropped"
    os.makedirs(outputFolder, exist_ok = True)
    os.makedirs(croppedImageFolder, exist_ok=True)

    #max image size is 640x640
    imageSize = "640x640"
    i=1

    #trim any points that are too close to each other
    route_points = trim_points_by_distance(route_points, minStep)

    #load Depth Anything v2 Model
    depthModel = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Metric-Outdoor-Small-hf")

    #load paddleOCR model
    ocrModel = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False)


    #get pictures from the longitude latitude points using streetview api and save them
    for (lat, log) in route_points:
        locationStr = f"{lat},{log}"
        url = f"https://maps.googleapis.com/maps/api/streetview/metadata?location={locationStr}&key={API_KEY}"
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            details = json.loads(response.content)
            locationStr = f"{details["location"]["lat"]},{details["location"]["lng"]}"
            log = details["location"]["lng"]
            lat = details["location"]["lat"]
        except Exception as e:
            print(e)       

        for headingMult in range(360//fov):
            url = f"https://maps.googleapis.com/maps/api/streetview?size={imageSize}&location={locationStr}&fov={fov}&pitch={pitchAngle}&key={API_KEY}&heading={fov*headingMult}&scale=2&radius=10"
            try:
                response = requests.get(url, stream=True)
                response.raise_for_status()
                imagePath = os.path.join(outputFolder, f"streetview_frame_{i}_heading_{fov*headingMult}.jpg")
                with open(imagePath, 'wb') as outfile:
                    outfile.write(response.content)

                #Sign Detection starts here
                for model in os.listdir(os.path.join(os.getcwd(), "models")):
                    found = detect_and_store(f"images/raw/streetview_frame_{i}_heading_{fov*headingMult}.jpg", f"models/{model}")
                    if(datafile != None):   
                        for sign, conf, shape in found:
                            strippedurl = f"https://maps.googleapis.com/maps/api/streetview?size={imageSize}&location={locationStr}&fov={fov}&pitch={pitchAngle}&key=#####&heading={fov*headingMult}&scale=2&radius=10"
                            depth, newBearing = get_detection_depth_and_heading(depthModel, imagePath, shape, fov*headingMult, fov)
                            sign_lat, sign_lon = adjustCoords(lat, log, newBearing, depth)
                            if sign in ocrSigns:
                                sign = ocr(shape, sign, f"images/raw/streetview_frame_{i}_heading_{fov*headingMult}.jpg",
                                        f"images/temp/cropped/crop_frame_{i}_heading_{fov*headingMult}_sign_{sign}.jpg", ocrModel, ocr_candidate_signs)
                            addToGISFormatTable(datafile, sign, sign_lat, sign_lon, newBearing)
            except Exception as e:
                print(e)
        i+=1




# physical drive with a GoPro camera
def drive_gopro(input_mp4, interval, datafile, ocr_candidate_signs = [], run_dir = None):    #prepare images folder
    if run_dir is None:     # safety net if someone calls this without a run folder
        run_dir = os.path.join("runs", datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    outputFolder = os.path.join(run_dir, "frames")
    croppedImageFolder = os.path.join(run_dir, "crops")
    detectionsFolder = os.path.join(run_dir, "detections")
    debug_path = os.path.join(run_dir, "debug_detections.csv")
    os.makedirs(outputFolder, exist_ok = True)
    os.makedirs(croppedImageFolder, exist_ok=True)
    os.makedirs(detectionsFolder, exist_ok=True)

    run_start = time.perf_counter()    # TIMING: stopwatch for the whole run

    #load Depth Anything v2 Model
    print("Loading Depth and OCR Models")
    depthModel = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Metric-Outdoor-Small-hf")
    #load paddleOCR model
    ocrModel = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        enable_mkldnn=False,
        use_textline_orientation=False)
    
    print("Loading YOLO models")
    yolo_models = {name: YOLO(os.path.join("models", name))
                   for name in sorted(os.listdir("models")) if name.endswith(".pt")}
    print(f"Loaded {len(yolo_models)} models: {list(yolo_models)}")
    
    setup_s = time.perf_counter() - run_start    # TIMING: setup = everything since run_start
    print(f"TIMING setup (load all models): {setup_s:.1f} s")    # TIMING
    
    print("Creating Frames from GoPro Footage")
    t_frames = time.perf_counter()    # TIMING
    frames = GoProFrames(input_mp4, outputFolder, interval)
    cut_s = time.perf_counter() - t_frames    # TIMING
    print(f"TIMING cutting {len(frames)} frames + GPS pairing: {cut_s:.1f} s")    # TIMING


    print("Analyzing Frames")
    print(f"OCR signs are: {ocr_candidate_signs}")
    frame_log = []    # TIMING: one entry per frame: (total, detect, depth, ocr)
    for (framesrc, lat, log, fov, heading) in frames:
        frame_start = time.perf_counter()    # TIMING
        detect_s = 0.0    # TIMING: running totals for THIS frame
        depth_s = 0.0
        ocr_s = 0.0
        fov = float(fov)
        located = lat is not None          # False = no trusted GPS for this frame
        if located:
            lat = float(lat)
            log = float(log)
        
        depth = None    # computed on first detection, so frames with no signs skip the depth model

        for model_name, yolo in yolo_models.items():
            t = time.perf_counter()    # TIMING
            found = detect_and_store(framesrc, yolo, save_dir=detectionsFolder)
            detect_s += time.perf_counter() - t    # TIMING
            if datafile is not None:
                for box_i, (sign, conf, shape) in enumerate(found):
                    if located:
                        if depth is None:
                            t = time.perf_counter()    # TIMING
                            depth = estimate_depth(depthModel, framesrc)
                            depth_s += time.perf_counter() - t    # TIMING
                        box_depth, newBearing = get_box_depth_and_bearing(depth, shape, heading, fov)
                        sign_lat, sign_lon = adjustCoords(lat, log, newBearing, box_depth)
                        print(f"Adding {sign} at ({sign_lat}, {sign_lon}) to {datafile} table!")
                    else:
                        # no trusted GPS: we can't place this sign, so skip depth, bearing and coordinates
                        box_depth = newBearing = sign_lat = sign_lon = None
                        print(f"Adding {sign} with UNKNOWN location to {datafile} table!")
                    #debug: check the label before we pass off to OCR
                    add_debug_row(debug_path, os.path.basename(framesrc), model_name,
                        sign, conf, shape, box_depth, newBearing, sign_lat, sign_lon)
                    
                    if sign in ocrSigns:
                        crop_name = f"{os.path.splitext(os.path.basename(framesrc))[0]}_{os.path.splitext(model_name)[0]}_box{box_i}.jpg"
                        t = time.perf_counter()    # TIMING
                        try:
                            sign = ocr(shape, sign, framesrc,
                                    os.path.join(croppedImageFolder, crop_name), ocrModel, ocr_candidate_signs)
                        except Exception as e:
                            print(f"OCR failed for {crop_name}, keeping detector label: {e}")
                        ocr_s += time.perf_counter() - t    # TIMING
                    print(f"The new sign after OCR is {sign}!")
                    addToGISFormatTable(datafile, sign, sign_lat, sign_lon, newBearing)
     
        total_s = time.perf_counter() - frame_start    # TIMING
        frame_log.append((total_s, detect_s, depth_s, ocr_s))    # TIMING
        print(f"TIMING frame {os.path.basename(framesrc)}: total {total_s:.1f} s | "
              f"detect {detect_s:.1f} | depth {depth_s:.1f} | ocr {ocr_s:.1f}")    # TIMING
    # TIMING: summary at the end of the run
    if frame_log:
        n = len(frame_log)
        avg = lambda i: sum(x[i] for x in frame_log) / n
        print("=" * 50)
        print(f"TIMING SUMMARY ({n} frames, {len(yolo_models)} YOLO models)")
        print(f"  setup (once per run):   {setup_s:.1f} s")
        print(f"  cutting frames:         {cut_s:.1f} s")
        print(f"  avg per frame, total:   {avg(0):.2f} s")
        print(f"  avg per frame, detect:  {avg(1):.2f} s")
        print(f"  avg per frame, depth:   {avg(2):.2f} s  (only frames with a detection)")
        print(f"  avg per frame, ocr:     {avg(3):.2f} s")
        print(f"  slowest frame:          {max(x[0] for x in frame_log):.1f} s")
        print(f"  whole run:              {time.perf_counter() - run_start:.1f} s")