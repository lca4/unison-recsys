#!/usr/bin/env python
import argparse
import random
import libunison.utils as utils

from math import fabs
from libunison.models import *
from similarity import similarity

"""
Generates a playlist based on a given tag by looking for tracks with the 
nearest tags.
Returns an unsorted list of tracks (DB-storage order).


How it works?

Compute the distance between the given track and another track of the user library
Select the track if the distance is small enough
(Once enough tracks are selected, return the playlist (TODO define "enough tracks"))


IDEAS
Filter the playlist by user ratings, if available.
Define filters syntax/criterions

"""


# Size is the max playlist length (e.g. less tracks than given size).
#===============================================================================
# def generatePlFromTag(user_id, tag, filter=None, size=None, sort=None):
#    
#    playlist = list()
#    
#    refvect, weight = utils.tag_features(tag)
#    print "vector associated with tag:"
#    print refvect
#    print
#    
#    # Fetch LibEntries
#    store = utils.get_store()
#    entries = store.find(LibEntry, (LibEntry.user_id == user_id) & LibEntry.is_valid & LibEntry.is_local)
#    for entry in entries:
#        added = False
#        dist
#        if entry.track.features is not None:
#            tagvect = utils.decode_features(entry.track.features)
#            dist = fabs(sum([refvect[i] * tagvect[i] for i in range(len(v1))]))
#            # Filters
#            if filter is not None:
#                if filter == 'rating>=4':
#                    if entry.rating >= 4:
#                        added = True
#                elif filter == 'rating>=5':
#                    if entry.rating >= 5:
#                        added = True
#            # No filtering
#            else:
#                added = True
#        if added:
#            prob = 1 - dist  # Associate a probability
#            playlist.append((entry, prob))
#            print "track added to playlist"
#            print
#    
#    # Randomizes the order and removes tracks until the desired length is reached
#    playlist = randomizePL(playlist)
#    if size is not None:
#        resized = False
#        while not resized:
#            for track in playlist:
#                if len(playlist) > size:
#                    if track[1] < random.random():
#                        playlist.remove(track)
#                else:
#                    resized = True 
#    
#    # Sorting
#    if sort is not None:
#        if sort == 'ratings':
#            playlist = sorted(playlist, key=lambda x: x[0].rating)
#        elif sort == 'proximity':
#            playlist = sorted(playlist, key=lambda x: x[1])
#            
#    return playlist
#===============================================================================


# Size is the max playlist length (e.g. less tracks than given size).
# For a track, the seed is the local_id
def plgenerator(user_id, type, seed, filter=None, size=None, sort=None):
    """ Generates a playlist based on the seed 
    
    ISSUE:
    * if no filter is given, the playlist contains all the tracks. The less liked 
      tracks and most far apart should be discarded. 
    """
    
    playlist = list()
    store = utils.get_store()
    
    if (type == 'tag'):
        refvect, weight = utils.tag_features(seed)
    elif (type == 'track'):
        track = store.find(LibEntry, (LibEntry.user_id == user_id) & LibEntry.is_valid & LibEntry.is_local & (LibEntry.local_id == seed))
        if (track is not None):
            refvect, weight = utils.track_features(track.track.features)
        else:
            #TODO Handle error
            return None
    else:
        #TODO Handle error
        # unsupported seed type
        return None
    if refvect is None:
        #TODO Handle error
        return None
            
    # Fetch LibEntries
    #store = utils.get_store()
    entries = store.find(LibEntry, (LibEntry.user_id == user_id) & LibEntry.is_valid & LibEntry.is_local)
    for entry in entries:
        added = False
        dist
        if entry.track.features is not None:
            tagvect = utils.decode_features(entry.track.features)
            dist = fabs(sum([refvect[i] * tagvect[i] for i in range(len(v1))]))
            # Filters
            if filter is not None:
                if filter == 'rating>=4':
                    if entry.rating >= 4:
                        added = True
                elif filter == 'rating>=5':
                    if entry.rating >= 5:
                        added = True
            # No filtering
            else:
                added = True
        if added:
            prob = 1 - dist  # Associate a probability
            playlist.append((entry, prob))
#            print "track added to playlist"
#            print
    
    # Randomizes the order and removes tracks until the desired length is reached
    playlist = randomizePL(playlist)
    if size is not None:
        resized = False
        while not resized:
            for track in playlist:
                if len(playlist) > size:
                    if track[1] < random.random():
                        playlist.remove(track)
                else:
                    resized = True 
    
    # Sorting
    if sort is not None:
        if sort == 'ratings':
            playlist = sorted(playlist, key=lambda x: x[0].rating)
        elif sort == 'proximity':
            playlist = sorted(playlist, key=lambda x: x[1])
            
    return playlist


# From http://smallbusiness.chron.com/randomize-list-python-26724.html
# Or maybe random.shuffle()? # http://docs.python.org/2/library/random.html#random.shuffle
def randomizePL(oldPL):
    newPL = list()
    for i in range(len(oldPL)):
        element = random.choice(oldPL)
        oldPL.remove(element)
        newPL.append(element)
    return newPL

def _parse_args():
    parser = argparse.ArgumentParser();
    parser.add_argument('userid', type=int);
    parser.add_argument('tag');
    return parser.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    generatePlFromTag(args.userid, args.tag)
