#!/usr/bin/env python
"""Geometrical stuff."""

import collections

from math import atan2, cos, pi, sin, sqrt, floor, fabs

# Mean earth radius in meters, according to
# http://en.wikipedia.org/wiki/Earth_radius#Mean_radius
EARTH_RADIUS = 6371009

#Used in earlier implementation
#LAT_THRESHOLD = 30 # seconds
#so if lat_sec bellongs to [0,15] => 0
#   if lat_sec bellongs to [15,45] => 30
#   if lat_sec bellongs to [45,60] => 60

#LON_THRESHOLD = 60 # seconds
#so if lon_sec bellongs to [0,30] => 0
#   if lon_sec bellongs to [30,60] => 60

#size of a cluster in meters
clusterHeight = 1000.0
clusterWidth = 1000.0




# Simple data structure to represent a point.
Point = collections.namedtuple('Point', 'lat lon')


def distance(a, b, radius=EARTH_RADIUS):
    """Compute the great-circle distance between two points.

    The two points are to be given in degrees, i.e. the standartd latitude /
    longitude notation. By default, we assume the radius of the sphere is the
    earth's average radius. The distance is returned in meters.
    """
    # Implementation note: this is the haversine formula.
    delta_lat = deg_to_rad(b.lat - a.lat)
    delta_lon = deg_to_rad(b.lon - a.lon)
    a_lat = deg_to_rad(a.lat)
    b_lat = deg_to_rad(b.lat)
    x = (sin(delta_lat / 2.0)**2
            + sin(delta_lon / 2.0)**2 * cos(a_lat) * cos(b_lat))
    return radius * (2 * atan2(sqrt(x), sqrt(1 - x)))


def deg_to_rad(angle):
    """Convert an angle from degree to radians."""
    return (2 * pi / 360) * angle

def rad_to_deg(angle):
    return (angle * 180) / pi

#added by Vincent and Louis
# point is a geometry.Point
def map_location_on_grid(point):

    #old implementation:

    # lat = point.lat
    # lon = point.lon

    # north = lat > 0
    # east = lon > 0
    
    # lat = fabs(lat)
    # lon = fabs(lon)

    # convert into sexadecimal notation and round
    # lat_deg = floor(lat)
    # lat = (lat - lat_deg)*60
    # lat_min = floor(lat)
    # lat = (lat - lat_min)*60
    # lat_sec = floor(lat)

    # lon_deg = floor(lon)
    # lon = (lon - lon_deg)*60
    # lon_min = floor(lon)
    # lon = (lon - lon_min)*60
    # lon_sec = floor(lon)

    # rouding according to threshold:
    # if (lat_sec < LAT_THRESHOLD/2):
        # lat_sec = 0
    # elif (lat_sec < 3*LAT_THRESHOLD/2):
        # lat_sec = LAT_THRESHOLD
    # else:
        # lat_sec = 0
        # lat_min += 1

    # if (lon_sec > LON_THRESHOLD/2):
        # lon_min += 1
    # lon_sec = 0

    # get back to decimal notation:
    # lat = lat_min + (lat_sec / 60.0)
    # lat = lat_deg + (lat / 60.0)

    # if not north:
        # lat = -lat

    # lon = lon_min + (lon_sec / 60.0)
    # lon = lon_deg + (lon / 60.0)

    # if not east:
        # lon = -lon
       
    # return Point(lat, lon)
    
    #new implementation:
    lat = point.lat;
    lon = point.lon;

    phi = deg_to_rad(lat)
    theta = deg_to_rad(lon)
    
    #The distance between two latitudes changes only a little bit depending
    #on where we are on the map, so we consider it as a constant.
    clusterVertAngle = clusterHeight / EARTH_RADIUS
    
    # Here we find the position of the nearest cluster.
    # phi/clusterVertAngle is the rational number of clusters that we need to cross in order to reach the user.
    # The mapping operation consists of taking the floor of that number, it maps the user to the nearest cluster on his/her
    # bottom left.
    clusterLat = floor(phi / clusterVertAngle) * clusterVertAngle
    
    if cos(phi) == 0:
        phi = phi + 0.0001
        
    if cos(clusterLat) == 0:
        clusterLat = clusterLat + 0.0001

    #This formula was derived from the need to adapt the amount of degrees needed to travel a distance of clusterWidth
    #meters along a specific latitude. The circonference of a given latitude gets smaller when you go in direction of a pole. 
    clusterLon = floor(theta / (clusterWidth / (EARTH_RADIUS * cos(phi)))) * clusterWidth / (EARTH_RADIUS * cos(clusterLat))

    return Point(rad_to_deg(clusterLat), rad_to_deg(clusterLon))
    

