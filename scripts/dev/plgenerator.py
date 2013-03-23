#!/usr/bin/env python
import argparse
import random
import libunison.utils as utils

from math import fabs
from libunison.models import *

"""
Generates a playlist based on a given tag by looking for tracks with the 
nearest tags.
Returns an unsorted list of tracks (DB-storage order).


How it works?

Compute the distance between the given track and another track of the user library (tagsimilarity.py)
Select the track if the distance is small enough (TODO define "small enough")
(Once enough tracks are selected, return the playlist (TODO define "enough tracks"))


IDEAS
Filter the playlist by user ratings, if available.
Define filters syntax/criterions

"""
# MAXDISTANCE = 0.3  # [0-1] the maximum distance allowed between the tags
# MAXLENGTH = 25

# Size is the max playlist length (e.g. less tracks than given size).
def main(user_id, tag, filter=None, size=None, sort=None):
    
    playlist = list()
    
    refvect, weight = utils.tag_features(tag)
    print "vector associated with tag:"
    print refvect
    print
    
    # Fetch LibEntries
    store = utils.get_store()
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
            print "track added to playlist"
            print
    
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
    main(args.userid, args.tag)
