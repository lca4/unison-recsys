#!/usr/bin/env python

from math import cos, pi, floor, fabs

#All distances are in meters
# Mean earth radius according to
# http://en.wikipedia.org/wiki/Earth_radius#Mean_radius
EARTH_RADIUS = 6371009

# These distances are computed by staying at the Earth's surface:
DISTANCE_BETWEEN_POLES = 20000000 #approximatively 20K km
CIRC_AT_EQUATOR = 2*pi*EARTH_RADIUS #approximatively 40K km

CLUSTER_HEIGHT = 200000
CLUSTER_WIDTH = 200000


class Layer:
    """Simple class representing a layer as we split the Earth into layers
       attributes:
           lat: latitude at the center of the layer
           index: index of the layer, starting at the equator (0). A higher index means
                  the cluster is closer to the North pole and vice versa."""
    def __init__(self, lat, index, numberOfClusters=0):
        self.lat = lat
        self.index = index
        self.numberOfClusters = numberOfClusters
        self.clusterDict = {}

class Cluster:
    def __init__(self, lat, lon, index):
        self.lat = lat
        self.lon = lon
        self.index = index

    

def deg_to_rad(angle):
    """Convert an angle from degree to radians."""
    return (2 * pi / 360.0) * angle


def circAtLat(lat):
    """Latitude must be a value between 0 and 90 degrees)."""
    return CIRC_AT_EQUATOR * cos(fabs(deg_to_rad(lat)))

def numberOfLayers():
    """The number is rounded down, this means that the last clusters
       (namely the ones at the poles) will be a bit larger. Plus it always
       returns an odd number so that there is a layer centered at the equator
       and then several pairs of layers at equal distances from the equator."""
    number = (int)(floor(DISTANCE_BETWEEN_POLES/(float)(CLUSTER_HEIGHT)))
    if (number == 0):
        number = 1 #here the layer is bigger than the available area, we will only use one.
    elif (number % 2 == 0):
        number -= 1
    return number

def numberOfClustersAtLayer(layerLat):
    """The number is rounded down, this means that the last clusters
       (namely the ones near the extreme -180, 180 longitudes) will be a bit larger.
       Plus it always returns an odd number so that there is a cluster centered at lon=0
       and then several pairs of layers at equal distances from the center."""
    number = (int)(floor(circAtLat(layerLat)/(float)(CLUSTER_WIDTH)))
    if (number == 0):
        number = 1 #here the cluster is bigger than the available area, we will only use one.
    elif (number % 2 == 0):
        number -= 1
    return number

def latRangeOfLayer():
    """WARNING this is the general range for layers. The last layers
       (namely the ones at the poles) will have a slightly bigger range"""
    return 180 / (float)(numberOfLayers())

def lonRangeOfCluster(nbClusters):
    return 360 / (float)(nbClusters)

def createLayers(layersDict):
    layerWidth = latRangeOfLayer()
    aLayer = None
    index = 0
    lat = 0
    #Creating the layers, except from the ones at the poles.
    #index 0:
    aLayer = Layer(lat,index, numberOfClustersAtLayer(fabs(lat)))
    createClustersInLayer(aLayer)
    layersDict[lat] = aLayer
    #the other ones: (1 and -1, then 2 and -2, etc...)
    nbLayers = numberOfLayers()
    if (nbLayers >= 5):
        for i in range(1, nbLayers-1):
            index = increaseIndex(index, i)
            lat = index * layerWidth
            aLayer = Layer(lat,index, numberOfClustersAtLayer(fabs(lat)))
            createClustersInLayer(aLayer)
            layersDict[lat] = aLayer
    
    if (nbLayers >= 3):
        #Creating the last ones separately:
        remainingLatitudeDegrees = 90 - fabs(lat)
        lat = fabs(lat) + (layerWidth/2.0) + (remainingLatitudeDegrees/2.0)
        index = increaseIndex(index, nbLayers-1)
        aLayer = Layer(lat,index, numberOfClustersAtLayer(fabs(lat)))
        createClustersInLayer(aLayer)
        layersDict[lat] = aLayer
        lat *= -1
        index = increaseIndex(index, nbLayers)
        aLayer = Layer(lat,index, numberOfClustersAtLayer(fabs(lat)))
        createClustersInLayer(aLayer)
        layersDict[lat] = aLayer
    

def increaseIndex(index, i):
    index *= -1
    if (i % 2 == 0):
        index +=1
    return index

def createClustersInLayer(layer):
    """similar to createLayers()"""
    layerLat = layer.lat
    nbClusters = layer.numberOfClusters
    clusterWidth = lonRangeOfCluster(nbClusters)
    clusterDict = layer.clusterDict
    
    lon = 0
    index = 0
    aCluster = Cluster(layerLat, lon, index)
    clusterDict[lon] = aCluster
    
    if (nbClusters >= 5):
        for i in range(1, nbClusters-1):
            index = increaseIndex(index, i)
            lon = index * clusterWidth
            aCluster = Cluster(layerLat, lon, index)
            clusterDict[lon] = aCluster
    
    #Creating the last ones separately:
#debug    print('nbCluster=' +str(nbClusters) +'   lon='+str(lon)+'   , clwidth/2 ='+str(clusterWidth/2.0))
    if (nbClusters >= 3):
        remainingLongitudeDegrees = 180 - fabs(lon)
        lon = fabs(lon) + (clusterWidth/2.0) + (remainingLongitudeDegrees/2.0)
        index = increaseIndex(index, nbClusters-1)
        aCluster = Cluster(layerLat, lon, index)
        clusterDict[lon] = aCluster
        lon *= -1
        index = increaseIndex(index, nbClusters)
        aCluster = Cluster(layerLat, lon, index)
        clusterDict[lon] = aCluster
    



def getLayersDict():
    layersDict = {}
    createLayers(layersDict)
    return layersDict

a=getLayersDict() #debug
print(len(a))
print('----')
for lat in reversed(sorted(iter(a))):
     print(len(a[lat].clusterDict))
#    s = '['
#    for lon in sorted(iter(a[lat].clusterDict)):
#        s= s + '(' + "{0:.2f}".format(lat) +', ' + "{0:.2f}".format(lon) + ')'
#    s = s + ']'
#    print(s)
