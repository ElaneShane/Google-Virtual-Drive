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

"""
GPS accuracy range: 3 to 10 meters; while the truck is moving having some kind of buffer for the GPS will prevent jitter and allow for more accurate sign placement. 
current buffer: 3 meters
"""

# gets how far point B is from Point A in meters
def distance_m(lat1, lon1, lat2, lon2):
    _, _, d = Geod(ellps="WGS84").inv(lon1, lat1, lon2, lat2) # inverse geodetic problem
    return d

# uses a ref point (last known good GPS location where heading was sucessfully calculated)
def update_heading(heading, ref, lat, lon, min_move_m=3.0):
    """Return (heading, ref). Heading only changes after moving >= min_move_m from ref."""
    if ref is None: # then this is the first frame
        return heading, (lat, lon)

    # if ditance is less than 3 meters then we assume that the camera has stoped moving or is moving too slow 
    # so it returns the old heading and the old reference point and we ignore this frame
    if distance_m(ref[0], ref[1], lat, lon) < min_move_m:
        return heading, ref
    # else, if the truck has moved more than 3 mteres fromthe ref point, then we can trust the movement for GPS
    # so we calculate the new heading and return it along with the new reference point for the next cycle
    return calculate_bearing(ref[0], ref[1], lat, lon), (lat, lon)


def heading_from_track(track, t, half_window=2.0, min_move_m=8.0, max_half_window=8.0):
    """Direction the truck is traveling at video time t.
    track: list of (video_seconds, lat, lon), sorted by time.
    Returns a bearing 0-360, or None if the truck didn't move enough."""
    hw = half_window
    while hw <= max_half_window:
        # nearest GPS point to "hw seconds before" and "hw seconds after" this frame
        # (near the ends of the clip, the nearest point is just the first/last one)
        before = min(track, key=lambda p: abs(p[0] - (t - hw)))
        after = min(track, key=lambda p: abs(p[0] - (t + hw)))
        # only trust the direction if the truck actually moved between the two points
        if distance_m(before[1], before[2], after[1], after[2]) >= min_move_m:
            return calculate_bearing(before[1], before[2], after[1], after[2])
        hw *= 2   # stopped or crawling: look at a wider window (2 -> 4 -> 8 seconds)
    return None   # never moved enough: heading unknown


def fill_missing_headings(headings):
    """Replace None entries with the nearest known heading (carry the last good one forward,
    and fill any Nones at the very start from the first good one)."""
    if all(h is None for h in headings):
        raise ValueError("No frame had a usable heading (the truck never moved?)")
    filled = list(headings)
    last = None
    for i, h in enumerate(filled):
        if h is None:
            filled[i] = last      # copy the previous good heading (may still be None at the start)
        else:
            last = h
    first_good = next(h for h in filled if h is not None)
    return [first_good if h is None else h for h in filled]

