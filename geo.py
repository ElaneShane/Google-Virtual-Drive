import math
from pyproj import Geod


#geometry functions

def sign_bearing(car_heading, box_center_x, image_width, hfov):
    """Bearing (0-360) from the camera to the sign
        car heading is in degrees [direction that the camera faces]
        box_center_x [x pixel of the center of the bounding box]
        image_width [width of the image the box came from in pixels]
        hfov [horizontal field of view of the camera in degrees]
    """
   
    # get how many pixels left or right the box is from the center
    # then convert the count into a fraction of the image width (-0.5 if its on the extreme left, and + 0.5 if its on the extreme right)
    offset = (box_center_x - image_width / 2) / image_width 

    # translate fraction into degrees of the horizontal field of view + the car heading --> to get final bearing
    return (car_heading + offset * hfov) % 360


def adjustCoords(lat, lon, bearing, depth):
    """Calculate exact coordinates given the GPS loc of the car, the compass direction to sign and how far the sign is
        lat, lon: latitude and longitude of the original point
        bearing: direction to move in degrees
        depth: distance to move in meters
    """
    geod = Geod(ellps="WGS84") # mathematical model of the earth
    lon, lat, _ = geod.fwd(lons=lon, lats=lat, az=bearing, dist=depth)
    return lat, lon


#use this with current point and next point to get bearing
def calculate_bearing(lat1, lon1, lat2, lon2):
    """
    Calculate the initial bearing (forward azimuth) between two GPS points, corrected to 0-360 degrees.
    
    Parameters:
        lat1, lon1 (float): Latitude and longitude of point 1 (decimal degrees).
        lat2, lon2 (float): Latitude and longitude of point 2 (decimal degrees).
    
    Returns:
        float: Bearing in degrees (0-360°).
    """
    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Difference in longitude
    delta_lon = lon2_rad - lon1_rad
    
    # Compute bearing in radians
    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
    bearing_rad = math.atan2(y, x)
    
    # Convert radians to degrees and adjust to 0-360°
    bearing_deg = math.degrees(bearing_rad)
    bearing_deg_corrected = (bearing_deg + 360) % 360  # Fix negative bearings
    
    return bearing_deg_corrected