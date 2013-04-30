#!/usr/bin/env python
# coding=utf-8
"""Single-user-related views."""

import datetime
import hashlib
import helpers
import libunison.geometry as geometry
import libunison.predict as predict
import time

import json
import libunison.utils as utils

from constants import errors
from flask import Blueprint, request, g, jsonify
from operator import itemgetter
from storm.expr import Desc, In

from math import fabs
from random import randint

from libunison.models import User, LibEntry, Playlist, PllibEntry, TopTag


solo_views = Blueprint('solo_views', __name__)


# Maximal number of groups returned when listing groups.
MAX_PLAYLISTS = 10


@solo_views.route('/<int:uid>/playlist', methods=['POST'])
@helpers.authenticate()
def generate_playlist(uid):
    """Generate a playlist from given seeds"""
    seeds = request.form['seeds']
    print 'solo_views.generate_playlist: seeds = %s' % seeds
    options = request.form['options'] # Can be missing
    print 'solo_views.generate_playlist: options = %s' % options
    
    if seeds is None:
        print 'solo_views.generate_playlist: BadRequest: seeds missing'
        raise helpers.BadRequest(errors.MISSING_FIELD, "seeds are missing")

    return pl_generator(uid, seeds, options)


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
# For a track, the seed is the local_id
def pl_generator(user_id, seeds, options = None): 
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
        print 'solo_views.pl_generator: seeds is None'
        raise Exception
    
    # Initiate some values
    playlist = list()
    store = utils.get_store()
    tagsmatrix = list()
    refvect = list()
    
    seeds = json.loads(seeds)
    print 'solo_views.pl_generator: seeds = %s' %(seeds)
    for entry in seeds.items(): # optimization possible, for e.g.: one JSONArray per type
        type = entry[0]
        seedslist = entry[1]
        print 'solo_views.pl_generator: type = %s, seedslist = %s' %(type, seedslist)
        if seedslist is not None:
            for seed in seedslist:
                if type == 'tags':
                    vect, weight = utils.tag_features(seed)
                if type == 'tracks':
                    # TODO: update find condition: UNVALID!
                    track = store.find(LibEntry, (LibEntry.user_id == user_id) & LibEntry.is_valid & LibEntry.is_local & (LibEntry.local_id == seed)) # Can't work: seed is not the local_id !
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
        for tagvect in tagsmatrix: # ugly, find something better
            sum += tagvect[i]
            refvect.append(sum)
    if refvect is None:
        #TODO Handle error
        print 'solo_views.pl_generator: refvect is None'
        raise Exception
    
    # Get options from input
    if options is not None:
        options = json.loads(options)
        try:
            filter = options.value('filter')
        except:
            filter = None
        try:
            size = option.value('size')
        except:
            size = None
        try:
            sort = option.value('sort')
        except:
            sort = None
    else:
        filter = None
        size = None
        sort = None
    
    # Fetch LibEntries
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
            print 'solo_views.pl_generator: added entry = %s to playlist' % entry
#            print "track added to playlist"
    
    if playlist is not None:
    
        # Randomizes the order
        playlist = pl_randomizer(playlist)
        
        # Removes tracks until the desired length is reached
        # Do it even is no size specifications? (not only random track order)
        if size is not None:
            resized = False
            while not resized: # improvement can be done here (use playlist.length() for eg.)
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
                
        # Remove the probabilities
        dirty = playlist
        del playlist
        for pair in dirty:
            playlist.append(pair[0])
            
        # Keep only the relevant fields from the tracks
        tracks = list()
        for entry in playlist:
            tracks.append({
              'artist': entry.track.artist,
              'title': entry.track.title,
              'local_id': entry.local_id,
            })
        
        # Store the playlist in the database
        pldb = Playlist(user_id, unicode('playlist_' + str(randint(0, 99))), size, seeds, unicode(refvect), jsonify(tracks=tracks))
        insert_id = g.store.add(pldb) # does it work?
        # Retrieve id from last insert to playlist table --> HOW?
        # Add it to the user library
        pledb = PllibEntry(user_id, 0)
        g.store.add(pledb)
        
        # Craft JSON
        playlistdescriptor = dict()
        playlistdescriptor['tracks'] = tracks
        # Add additional data
        playlistdescriptor['gs_playlist_id'] = None # TODO
        playlistdescriptor['author_id'] = user_id
        playlistdescriptor['size'] = size
        playlistdescriptor['gs_creation_time'] = None #TODO
        playlistdescriptor['gs_update_time'] = None #TODO
        
        print 'solo_views.pl_generator: playlist = %s' % playlist
        return playlistdescriptor
    return None


# From http://smallbusiness.chron.com/randomize-list-python-26724.html
# Or maybe random.shuffle()? # http://docs.python.org/2/library/random.html#random.shuffle
def pl_randomizer(oldPL):
    newPL = list()
    for i in range(len(oldPL)):
        element = random.choice(oldPL)
        oldPL.remove(element)
        newPL.append(element)
    return newPL

# @solo_views.route('/<int:uid>/playlist', methods=['POST'])
# @helpers.authenticate()
# def create_playlist(uid):
#     #TODO
#     raise helpers.BadRequest(errors.MISSING_FIELD, "not yet available")
#     return None
# 
# 
# @solo_views.route('/<int:uid>/playlists/<int:pid>', methods=['GET'])
# @helpers.authenticate(with_user=True)
# def get_playlist(uid, pid):
#     #TODO
#     raise helpers.BadRequest(errors.MISSING_FIELD, "not yet available")
#     return None
# 
# Returns the list of playlists of user uid
@solo_views.route('/<int:uid>/playlists', methods=['GET'])
@helpers.authenticate()
def list_playlists(uid):
    playlists = list()
    rows = sorted(g.store.find(PllibEntry, (PllibEntry.user_id == uid) & PllibEntry.is_valid)) #TODO JOIN ON Playlist.is_shared = True
    for playlist in rows[:MAX_PLAYLISTS]:
        playlists.append({
          'pid': playlist.playlist.id,
          'created': playlist.playlist.created,
          'updated': playlist.playlist.updated,
          'title': playlist.playlist.title,
          'image': playlist.playlist.image,
          'author_id': playlist.playlist.author.id,
          'author_name': playlist.playlist.author.nickname,
          'size': playlist.playlist.size,
          'tracks': playlist.playlist.tracks,
          'listeners': playlist.playlist.listeners,
          'avg_rating': playlist.playlist.avg_rating,
          'shared': playlist.playlist.is_shared,
          'synced': playlist.is_synced,
          'rating': playlist.rating,
          'comment': playlist.comment
        })
    #raise helpers.BadRequest(errors.MISSING_FIELD, "not yet available")
    return jsonify(playlists=playlists)
# 
# 
# # Updates the playlist plid from user uid
# @solo_views.route('/<int:uid>/playlists/<int:plid>', methods=['POST'])
# @helpers.authenticate()
# def update_playlist(uid, plid):
#     #TODO
#     raise helpers.BadRequest(errors.MISSING_FIELD, "not yet available")
#     return None
# 
# 
# # Disables the playlist plid from user uid
# @solo_views.route('/<int:uid>/playlists/<int:plid>', methods=['POST'])
# @helpers.authenticate()
# def remove_playlist(uid, plid):
#     #TODO
#     raise helpers.BadRequest(errors.MISSING_FIELD, "not yet available")
#     return None

# Returns the list of tags
@solo_views.route('/tags', methods=['GET'])
@helpers.authenticate()
def list_tags():
    
    tags = list()
    
    # TESTS
    tags.append({
                 'tid': 1,
                 'name': 'rock',
                 'ref_id': 1234567890
                 })
    tags.append({
                 'tid': 2,
                 'name': 'pop',
                 'ref_id': 1357924680
                 })
    
    
#     store = utils.get_store()
#     entries = store.find(TopTag, None)
#     for entry in entries:
#         #TODO
#         print TODO
    #raise helpers.BadRequest(errors.MISSING_FIELD, "not yet available")
    return jsonify(tags=tags)
