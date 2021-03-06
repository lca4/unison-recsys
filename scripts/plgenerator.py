#!/usr/bin/env python
import argparse
import random
import json

from math import fabs
from libunison.models import *
import libunison.utils as utils
from similarity import similarity

"""

DO NOT USE ANYMORE

DO NOT USE ANYMORE

DO NOT USE ANYMORE

DO NOT USE ANYMORE

DO NOT USE ANYMORE

DO NOT USE ANYMORE


USE solo_views INSTEAD



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
# For a track, the seed is the local_id
def plgenerator(user_id, seeds, options): 
                #seeds, filter='rating>=4', size=None, sort=None):
    """ Generates a playlist based on the seed 
    
    ISSUE:
    * if no filter is given, the playlist contains all the tracks. The less liked 
      tracks and most far apart should be discarded. => default filter: rating>=4
      
    IMPROVEMENT (to be used from now on):
    The type of seed is no more explicitly given, it is integrated into the list
    of seeds. The seeds are stored in a JSONObject of JSONObject tuples in the 
    form {"type":<type>,"seed":<seed>}
    """
    # In order to test my generator, I first implement it for the tags. The tracks
    # will come later.
    
    # Check the input
    #TODO check user_id in DB?
    if seeds is None:
        #TODO Handle error
        print 'plgenerator.plgenerator: seeds is Noe'
        return None
#     entity = json.loads(json)
#     seedscontainer = entity['seeds']
#     if seedscontainer is None:
#         #TODO handle error
#         return None
    
    # Initiate some values
    playlist = list()
    store = utils.get_store()
    tagsmatrix = list()
    refvect = list()
    
    seeds = json.loads(seeds)
    for entry in seeds.items(): # optimization possible, for e.g.: one JSONArray per type
        type = entry[0]
        seedslist = entry[1]
        print 'plgenerator.plgenerator: type = %s, seedslist = %s' %(type, seedslist)
        if seedslist is not None:
            for seed in seedslist:
                if type == 'tags':
                    vect, weight = utils.tag_features(seed)
                if type == 'tracks':
                    track = store.find(LibEntry, (LibEntry.user_id == user_id) & LibEntry.is_valid & LibEntry.is_local & (LibEntry.local_id == seed))
                    if (track is not None):
                        vect, weight = utils.track_features(track.track.features)
                    else:
                        #TODO Handle error
                        vect = list()
                else:
                    #TODO handle error: undefined seed type
                    vect = list()
            tagsmatrix.append(vect)
        
    for i in xrange(len(tagsmatrix[0])):
        sum = 0
        for tagvect in tagsmatrix: # moche, trouver qqch de plus raffiné
            sum += tagvect[i]
            refvect.append(sum)
        #TODO normalize refvect
    if refvect is None:
        #TODO Handle error
        print 'plgenerator.plgenerator: refvect is None'
        return None
    
    # Fetch LibEntries
    entries = store.find(LibEntry, (LibEntry.user_id == user_id) & LibEntry.is_valid & LibEntry.is_local)
    for entry in entries:
        added = False
        dist
        if entry.track.features is not None:
            tagvect = utils.decode_features(entry.track.features)
            dist = fabs(sum([refvect[i] * tagvect[i] for i in range(len(v1))]))
            #TODO normalize
            # Filters
            filter = None #TODO pick from options
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
            print 'plgenerator.plgenerator: added entry = %s to playlist' % entry
    
    # Randomizes the order and removes tracks until the desired length is reached
    playlist = randomizePL(playlist)
    
    size = None #TODO pick from options
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
    sort = None #TODO pick from options
    if sort is not None:
        if sort == 'ratings':
            playlist = sorted(playlist, key=lambda x: x[0].rating)
        elif sort == 'proximity':
            playlist = sorted(playlist, key=lambda x: x[1])

    print 'plgenerator.plgenerator: playlist = %s' % playlist
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
