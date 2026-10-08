import polyline
import requests
import os
import csv
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
def drive_gopro(input_mp4, interval, datafile, ocr_candidate_signs = []):
    #prepare images folder
    print("Preparing Directories")
    outputFolder = "images/raw"
    croppedImageFolder = "images/temp/cropped"
    os.makedirs(outputFolder, exist_ok = True)
    os.makedirs(croppedImageFolder, exist_ok=True)

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

    print("Creating Frames from GoPro Footage")
    frames = GoProFrames(input_mp4, outputFolder, interval)
    #set initial heading from location 1 to 2
    heading = calculate_bearing(float(frames[0][1]), float(frames[0][2]), float(frames[1][1]), float(frames[1][2]))
    previousLocation = None

    print("Analyzing Frames")
    print(f"OCR signs are: {ocr_candidate_signs}")
    for (framesrc, lat, log, fov) in frames:
        fov = float(fov)
        lat = float(lat)
        log = float(log)
        heading, previousLocation = update_heading(heading, previousLocation, lat, log)
        depth = None    # computed on first detection, so frames with no signs skip the depth model

        for model_name, yolo in yolo_models.items():
            found = detect_and_store(framesrc, yolo)
            if datafile is not None:
                for box_i, (sign, conf, shape) in enumerate(found):
                    if depth is None:
                        depth = estimate_depth(depthModel, framesrc)
                    box_depth, newBearing = get_box_depth_and_bearing(depth, shape, heading, fov)
                    sign_lat, sign_lon = adjustCoords(lat, log, newBearing, box_depth)
                    print(f"Adding {sign} at ({sign_lat}, {sign_lon}) to {datafile} table!")
                    #debug: check the label before we pass off to OCR
                    add_debug_row("tables/debug_detections.csv", os.path.basename(framesrc), model_name,
                        sign, conf, shape, box_depth, newBearing, sign_lat, sign_lon)
                    if sign in ocrSigns:
                        crop_name = f"{os.path.splitext(os.path.basename(framesrc))[0]}_{os.path.splitext(model_name)[0]}_box{box_i}.jpg"
                        try:
                            sign = ocr(shape, sign, framesrc,
                                    os.path.join("images/temp/cropped", crop_name), ocrModel, ocr_candidate_signs)
                        except Exception as e:
                            print(f"OCR failed for {crop_name}, keeping detector label: {e}")
                    print(f"The new sign after OCR is {sign}!")
                    addToGISFormatTable(datafile, sign, sign_lat, sign_lon, newBearing)