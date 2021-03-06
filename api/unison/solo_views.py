#!/usr/bin/env python
# coding=utf-8
# author=Marc Bourqui
"""Single-user-related views."""

import datetime
import hashlib
import helpers
import libunison.geometry as geometry
import libunison.predict as predict
import time
import copy

import json
import libunison.utils as utils

from constants import errors
from flask import Blueprint, request, g, jsonify
from operator import itemgetter
from storm.expr import Desc, In

from math import fabs, sqrt
from random import randint, random, choice

from libunison.models import User, LibEntry, Playlist, PllibEntry, TopTag

solo_views = Blueprint('solo_views', __name__)

# Maximal number of groups returned when listing groups.
MAX_PLAYLISTS = 10


@solo_views.route('/<int:uid>/playlist', methods=['POST'])
@helpers.authenticate()
def generate_playlist(uid):
    """Generates a playlist from given seeds"""
    seeds = request.form['seeds']       # Mandatory
    options = request.form['options']   # Optional (can be missing)
    
    if seeds is None:
        print 'solo_views.generate_playlist: BadRequest: seeds missing'
        raise helpers.BadRequest(errors.MISSING_FIELD, "Seeds are missing")

    try:
        playlist = pl_generator(uid, seeds, options)
        if playlist is not None and playlist:
            return jsonify(playlist)
    except helpers.NotFound, nf:
        if nf.error == errors.IS_EMPTY:
            print 'solo_views.pl_generator: Could not generate a playlist for user %d from seeds %s with options %s: no tracks found in user library' % (uid, seeds, options)
            raise helpers.NotFound(errors.IS_EMPTY, nf.msg)
        elif nf.error == errors.NO_TAGGED_TRACKS:
            print 'solo_views.pl_generator: user %s has no tagged tracks' % user_id
            raise helpers.NotFound(errors.NOT_TAGGED_TRACKS, nf.msg)
        else:
            print 'solo_views.pl_generator: User %d : Undefined exception: %s with message %s' % (nf.error, nf.msg)

@solo_views.route('/<int:uid>/playlists', methods=['GET'])
@helpers.authenticate()
def list_user_playlists(uid):
    """Lists the playlists created by the user uid"""
    playlists = list()
    # Don't show playlists still stored on phone (aka local_id is set)
    rows = sorted(g.store.find(PllibEntry, (PllibEntry.user == uid) & PllibEntry.is_valid & (PllibEntry.local_id == None)))
    if rows is not None and rows:
        for playlist in rows[:MAX_PLAYLISTS]:
            playlists.append(to_dict(playlist))
        return jsonify(playlists=playlists)
    else:
        print 'solo_views.list_user_playlists: User %d has no playlist' % uid
        raise helpers.NotFound(errors.IS_EMPTY, "User has no playlist")

@solo_views.route('/<int:uid>/playlists/shared', methods=['GET'])
@helpers.authenticate()
def list_shared_playlists(uid):
    """Lists the playlists available to everyone."""
    playlists = list()
    rows = sorted(g.store.find(Playlist, (Playlist.author_id != uid) & Playlist.is_valid & Playlist.is_shared))
    if rows is not None and rows:
        for playlist in rows[:MAX_PLAYLISTS]:
            playlists.append(to_dict(playlist))
        return jsonify(playlists=playlists)
    else:
        print 'solo_views.list_shared_playlists: no shared playlists with user %d' % uid
        raise helpers.NotFound(errors.IS_EMPTY, "No playlist shared with the user")



@solo_views.route('/<int:uid>/playlist/<int:plid>', methods=['POST'])
@helpers.authenticate()
def update_playlist(uid, plid):
    """
    Updates the playlist plid from user uid.
    
    Fields to be updted are optional.
    
    Supported fields:
        * local_id [int]
        * title [Unicode]
        * image [Unicode]
        * tracks [JSONObject]
        * delta [JSONObject]
    """
    # Updates are only allowed if user is author of playlist
    entry = g.store.find(Playlist, (Playlist.author_id == uid) & (Playlist.id == plid ) & Playlist.is_valid).one()
    if entry is not None and entry:
        fields = request.form['fields']
        if fields:
            fields = json.loads(fields)
            for field in fields.items():
                key = field[0]
                value = field[1]
                if key == 'title':
                    entry.set(title=unicode(value))
                elif key == 'image':
                    entry.set(image=unicode(value))
                elif key == 'local_id':
                    if value is not None:
                        value = int(value)
                    g.store.find(PllibEntry, (PllibEntry.user_id == uid) & (PllibEntry.playlist_id == plid) & PllibEntry.is_valid).set(local_id=value)
                elif key == 'tracks':
                    entry.set(tracks=value)
                elif key == 'delta':
                    # WORK IN PROGRESS
                    try:
                        delta = json.loads(value)
                        delta_type = delta['type']
                        artist = delta['entry']['artist']
                        title = delta['entry']['title']
                        local_id = int(delta['entry']['local_id'])
                        play_order = int(delta['entry']['play_order'])
                    except:
                        raise helpers.BadRequest(errors.INVALID_DELTA,
                                "not a valid playlist library delta")
                    current_entries = local_valid_entries(user)
                    key = hashlib.sha1(artist.encode('utf-8')
                                       + title.encode('utf-8') + str(local_id)).digest()
                    if delta_type == 'PUT':
                        if key not in current_entries:
                            set_lib_entry(user, artist, title, local_id=local_id)
                    elif delta_type == 'DELETE':
                        if key in current_entries:
                            current_entries[key].is_valid = False
                    else:
                        # Unknown delta type.
                        print 'solo_views.update_playlist: invalid delta "%s" for playlist %s' % (delta_type, uid) 
                        raise helpers.BadRequest(errors.INVALID_DELTA,
                                "not a valid library delta")
            g.store.commit()
            return helpers.success()
    print 'solo_views.update_playlist: invalid delta'
    raise helpers.NotFound(errors.OPERATION_FAILED, "Failed to update the playlist with id %d, please check if user is author." % uid)
 

@solo_views.route('/<int:uid>/playlist/<int:plid>', methods=['DELETE'])
@helpers.authenticate()
def remove_playlist(uid, plid):
    """
    Disables the playlist plid from user uid playlist library.
    """
    removed = g.store.find(PllibEntry, (PllibEntry.user == uid) & (PllibEntry.playlist == plid) & PllibEntry.is_valid).one()
    if removed is not None and removed:
        removed.is_valid = False
        g.store.commit()
        return helpers.success()
    else:
        print 'solo_views.remove_playlist: Failed to remove playlist %d for user %d' % (plid, uid)
        raise helpers.NotFound(errors.IS_EMPTY, "Failed to find playlist %d for user %d" % (plid, uid))

@solo_views.route('/<int:uid>/playlist/<int:plid>/copy', methods=['POST'])
@helpers.authenticate()
def copy_playlist(uid, plid):
    """
    Copies a shared playlist to the user library.
    
    This is not a deep copy, in order to avoid a playlist containing tracks not 
    available in the user library. To achieve this, a new playlist is generated 
    based on the seeds and options from the original one.
    """
    pl = g.store.find(Playlist, (Playlist.id == plid) & Playlist.is_valid & Playlist.is_shared).one()
    playlist = jsonify(pl_generator(uid, pl.seeds, pl.options))
    if playlist is not None and playlist:
        return playlist
    else:
        print 'solo_views.copy_playlist: copy of playlist %d failed for user %d' % (plid, uid)
        raise helpers.NotFound(errors.IS_EMPTY, "Failed to copy playlist")


@solo_views.route('/tags/top', methods=['GET'])
@helpers.authenticate()
def list_top_tags():
    """
    Lists the top tags 
    """
    
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
    tags.append({
                 'tid': 3,
                 'name': 'dance',
                 'ref_id': 2468013579
                 })
    tags.append({
                 'tid': 4,
                 'name': 'electronic',
                 'ref_id': 1256903478
                 })
    tags.append({
                 'tid': 5,
                 'name': 'alternative',
                 'ref_id': 3478125690
                 })
    tags.append({
                 'tid': 6,
                 'name': 'disco',
                 'ref_id': 6789012345
                 })
    
    
#     store = utils.get_store()
#     entries = store.find(TopTag, None)
#     for entry in entries:
#         #TODO
#         print TODO
    #raise helpers.BadRequest(errors.MISSING_FIELD, "not yet available")
    return jsonify(tags=tags)


# Class functions (not part of the api itself)

def pl_generator(user_id, seeds, options = None):
    """ Generates a playlist based on the given seeds.
    
    The playlist is generated by fetching the tracks with the nearest tags to 
    the seeds.
    
    The seeds are stored in a JSONObject of tuples in the form
    {<type>:<seeds>[, ...]}
    Supported types:
        * Tags
    
    The options are stored in a JSONObject of tuples in the form
    {<option>:<value>[, ...]}
    Supported options:
        * Filter
            Available values:
            - rating>=3 [default]
            - rating>=4
            - rating>=5
        * Size (to be extended)
            Available value:
            - probabilistic [default]
        * Sort
            Available values:
            - natural [default]
            - ratings
            - proximity
        * Unrated
            Available values:
            - True [default]
            - False
        * Title
          The given value is the title to be set to the playlist
    """
    
    # Set some default values
    default_filter = 'rating>=3'    # [rating>=3|rating>=4|rating>=5]
    default_size = 'probabilistic'  # [probabilistic|ratings|proximity]
    default_sort = 'natural'        # [natural]
    default_unrated = True          # [True|False]
    default_title = '__unnamed__><((()>' # Reduce probability user chooses the same name 
    
    # Check the input
    if seeds is None or not seeds:
        #TODO Handle error
        print 'solo_views.pl_generator: seeds is None'
        raise Exception
    
    # Initiate some values
    probpl = list() # probabilistic playlist aka playlist with probabilities associated to each tracks
    playlist = list() # pure playlist (only data relative to playlist)
#     store = utils.get_store()
    tagsmatrix = list()
    refvect = list()
    
    seeds = json.loads(seeds)
    for entry in seeds.items():
        type = entry[0]
        seedslist = entry[1]
        #seedslist.append(entry[1]) # avoids missinterpreting one-element lists
        if seedslist is not None:
            for seed in seedslist:
                if type == 'tags':
                    vect, weight = utils.tag_features(seed)
                # Selection by tracks is not available for now
#                 if type == 'tracks':
#                     # TODO: update find condition: UNVALID!
#                     track = store.find(LibEntry, (LibEntry.user_id == user_id) & LibEntry.is_valid & LibEntry.is_local & (LibEntry.local_id == seed)) # Can't work: seed is not the local_id !
#                     if (track is not None):
#                         vect, weight = utils.track_features(track.track.features)
#                         print 'solo_views.pl_generator: added features for track %s to refvect' %(track.track.title)
#                     else:
#                         #TODO Handle error
#                         vect = list()
                else:
                    #TODO handle error: undefined seed type
                    print 'solo_views.pl_generator: unknown type of tag: %s' % type
                    vect = list()
            tagsmatrix.append(vect)
        
    for i in xrange(len(tagsmatrix[0])):
        vsum = 0
        for tagvect in tagsmatrix: # ugly, find something better, like sympy
            vsum += tagvect[i]
            refvect.append(vsum)
        # Normalization
        refvect = normalize(refvect)
    if refvect is None or not refvect:
        #TODO Handle error
        print 'solo_views.pl_generator: refvect is None'
        raise Exception
    
    # Get options from input
    if options is not None and options:
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
        try:
            unrated = option.value('unrated')
        except:
            unrated = None
        try:
            title = option.value('title')
        except:
            title = None
    else:
        filter = None
        size = None
        sort = None
        unrated = None
        title = None
    # Set default values
    if filter is None:
        filter = default_filter
    if size is None:
        size = default_size
    if sort is None:
        sort = default_sort
    if unrated is None:
        unrated = default_unrated
    if title is None:
        title = default_title

    # Fetch LibEntries
    if unrated:
        entries = g.store.find(LibEntry, (LibEntry.user_id == user_id) & LibEntry.is_valid & LibEntry.is_local)
    else:
        # TODO find if possibility to filter on existing result set entries.
        entries = g.store.find(LibEntry, (LibEntry.user_id == user_id) & LibEntry.is_valid & LibEntry.is_local & (LibEntry.rating != None) & (LibEntry.rating > 0))
    if entries.any() is not None and entries.any():
        for entry in entries:
            added = False
            proximity=0 # 0=far away, 1=identical
            if entry.track.features is not None:
                tagvect = utils.decode_features(entry.track.features)
                # Not sure if tagvect is normalized, so in doubt normalize it.
                tagvect = normalize(tagvect)
                # Compute cosine similarity (dot product), and "normalize" it in [0,1]
                proximity = sum( [ fabs(sum([refvect[i] * tagvect[i] for i in range(len(tagvect))])), 1 ] ) / 2
                # TODO optimization: filter ASAP, to avoid useless computations
                # Ideal: filter at find() time
                
                # Filters
                if filter is not None:
                    if entry.rating == None:
                        if unrated:
                            added = True
                    else:
                        if unrated and (entry.rating <= 0):
                            added = True
                        if not added:
                            if filter == 'rating>=3':
                                if entry.rating >= 3 :
                                    added = True
                            elif filter == 'rating>=4':
                                if entry.rating >= 4 :
                                    added = True
                            elif filter == 'rating>=5':
                                if entry.rating >= 5 :
                                    added = True
                # No filtering
                else:
                    added = True
                if added:
                    prob = proximity  # Associate a probability
                    if (size != 'probabilistic') or (size == 'probabilistic' and prob >= random()) :
                        probpl.append((entry, prob))
            else:
                raise helpers.NotFound(errors.NO_TAGGED_TRACKS, "Could not generate a playlist: no tagged tracks were found.")
        if probpl is not None and probpl:
            # Randomize the order before reshaping
            probpl = pl_randomizer(probpl)
            
            # Here should happen the size reshaping
            # Idea: parse the size if not probabilistic to fetch the criteria
            # Criterion could be: [>|<]=XX% of probpl; [>|<]=XX (fixed length);
            
            # Sorting
            if sort is not None and sort:
                if sort == 'ratings':
                    probpl = sorted(probpl, key=lambda x: x[0].rating)
                elif sort == 'proximity':
                    probpl = sorted(probpl, key=lambda x: x[1])
                # Default: 'natural' sorting, does nothing (aka random)
                    
            # Remove the probabilities
            for pair in probpl:
                playlist.append(pair[0])
                
            # Keep only the relevant fields from the tracks
            tracks = list()
            index = 1 # First index
            for entry in playlist:
                tracks.append({
                  'artist': entry.track.artist,
                  'title': entry.track.title,
                  'local_id': entry.local_id,
                  'play_order': index # Postion of the track in the playlist, used by android
                })
                index = index + 1
            
            # Store the playlist in the playlist table
            jsonify(tracks=tracks)
            pldb = Playlist(user_id, unicode(title), len(playlist), seeds, options, unicode(refvect), tracks)
            g.store.add(pldb)
            g.store.flush() # See Storm Tutorial: https://storm.canonical.com/Tutorial#Flushing
            if title == default_title:
                g.store.find(Playlist, Playlist.id == pldb.id).set(title=u"playlist_%s" % pldb.id)
            # Add it to the user playlist library
            pledb = PllibEntry(user_id, pldb.id)
            g.store.add(pledb)
            g.store.flush()
            
            # Make the changes persistent in the DB, see Storm Tutorial: https://storm.canonical.com/Tutorial#Committing
            g.store.commit()
            
            # Craft JSON
            playlistdescriptor = to_dict(pledb)
            return playlistdescriptor
    raise helpers.NotFound(errors.IS_EMPTY, "Could not generate a playlist: no tracks were found in user library.")
#     return None

# From http://smallbusiness.chron.com/randomize-list-python-26724.html
# Or maybe random.shuffle()? # http://docs.python.org/2/library/random.html#random.shuffle
def pl_randomizer(oldPL):
    newPL = list()
    for i in range(len(oldPL)):
        element = choice(oldPL)
        oldPL.remove(element)
        newPL.append(element)
    return newPL

def to_dict(pllibentry):
    return {
          'gs_playlist_id': pllibentry.playlist.id,
          'gs_creation_time': pllibentry.playlist.created.replace(microsecond=0).isoformat(), # The replace(microsecond=0) trick avoids microseconds in iso format
          'gs_update_time': pllibentry.playlist.updated.replace(microsecond=0).isoformat(),
          'title': pllibentry.playlist.title,
          'image': pllibentry.playlist.image,
          'author_id': pllibentry.playlist.author.id,
          'author_name': pllibentry.playlist.author.nickname,
          'gs_size': pllibentry.playlist.size,
          'tracks': pllibentry.playlist.tracks,
          'gs_listeners': pllibentry.playlist.listeners,
          'gs_avg_rating': pllibentry.playlist.avg_rating,
          'gs_is_shared': pllibentry.playlist.is_shared,
          'gs_is_synced': pllibentry.is_synced,
          'user_rating': pllibentry.rating,
          'user_comment': pllibentry.comment
        }

def local_valid_entries(user, plid):
    entrydict = dict()
    pl = g.store.find(PllibEntry, (PllibEntry.user.id == user)
            & (PllibEntry.playlist.id == plid) & PllibEntry.is_local & PllibEntry.is_valid).one()
    for lib_entry in json.loads(pl.tracks):
        key = hashlib.sha1(lib_entry.track.artist.encode('utf-8')
                + lib_entry.track.title.encode('utf-8')
                + str(lib_entry.local_id)
                + str(lib_entry.play_order)).digest()
        entrydict[key] = lib_entry
    return entrydict

def normalize(vector):
    norm = sqrt(sum([x*x for x in vector]))
    if norm > 0:
        vector = [x / norm for x in vector]
    return vector;
    