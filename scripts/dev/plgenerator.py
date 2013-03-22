#!/usr/bin/env python
import argparse
import libunison.utils as utils

from math import fabs
from libunison.models import *

"""
Generates a playlist based on a given tag by looking for tracks with the 
nearest tags


How it works?

Compute the distance between the given track and another track of the user library (tagsimilarity.py)
Select the track if the distance is small enough (TODO define "small enough")
(Once enough tracks are selected, return the playlist (TODO define "enough tracks"))


IDEAS
Filter the playlist by user ratings, if available.
Define filters syntax/criterions

"""
MAXDISTANCE = 0.3  # [0-1] the maximum distance allowed between the tags

def main(user_id, tag, filter=None):
    refvect, weight = utils.tag_features(tag)
    print "vector associated with tag:"
    print refvect
    print
    tracks = list()
    playlist = list()
    store = utils.get_store()
    entries = store.find(LibEntry, (LibEntry.user_id == user_id) & LibEntry.is_valid & LibEntry.is_local)
    for entry in entries:
        added = False
        if entry.track.features is not None:
            tagvect = utils.decode_features(entry.track.features)
            if fabs(sum([refvect[i] * tagvect[i] for i in range(len(v1))])) <= MAXDISTANCE:
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
            playlist.append(entry)
            print "track added to playlist"
            print
            
    return playlist


def _parse_args():
    parser = argparse.ArgumentParser();
    parser.add_argument('userid', type=int);
    parser.add_argument('tag');
    return parser.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    main(args.userid, args.tag)
