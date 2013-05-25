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

from math import fabs
from random import randint, random, choice

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

    return jsonify(pl_generator(uid, seeds, options))


@solo_views.route('/<int:uid>/playlists', methods=['GET'])
@helpers.authenticate()
def list_user_playlists(uid):
    """
    Lists the playlists created by the user uid
    """
    playlists = list()
    # Don't show playlists still stored on phone (aka local_id is set)
    rows = sorted(g.store.find(PllibEntry, (PllibEntry.user == uid) & PllibEntry.is_valid & (PllibEntry.local_id is None)))
    for playlist in rows[:MAX_PLAYLISTS]:
        playlists.append(to_dict(playlist))
    return jsonify(playlists=playlists)


@solo_views.route('/playlists/shared', methods=['GET'])
@helpers.authenticate()
def list_shared_playlists():
    """
    Lists the playlists available to everyone.
    """
    playlists = list()
    rows = sorted(g.store.find(Playlist, (Playlist.author_id != uid) & Playlist.is_valid & Playlist.is_shared))
    for playlist in rows[:MAX_PLAYLISTS]:
        playlists.append(to_dict(playlist))
    return jsonify(playlists=playlists)


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
                print 'solo_views.update_playlist: fields = %s' % fields
            g.store.commit()
            return helpers.success()
    return None
 

@solo_views.route('/<int:uid>/playlists/<int:plid>', methods=['DELETE'])
@helpers.authenticate()
def remove_playlist(uid, plid):
    """
    Disables the playlist plid from user uid playlist library.
    """
    g.store.find(PllibEntry, (PllibEntry.user_id == uid) & (PllibEntry.playlist_id == plid) & PllibEntry.is_valid).set(is_valid=False)
    g.store.commit()
    return helpers.success()

@solo_views.route('/<int:uid>/playlist/<int:plid>/copy', methods=['POST'])
@helpers.authenticate()
def copy_playlist(uid, plid):
    
    # IDEA
    # Copy the seeds used to generate the original PL, and generate a PL with
    # these seeds, such that the PL contains only songs from the user library
    pl = g.store.find(Playlist, (Playlist.id == plid) & Playlist.is_valid & Playlist.is_shared).one()
    if seeds:
        return jsonify(pl_generator(uid, pl.seeds, pl.options))
    return None


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
            - rating>=3
            - rating>=4 [default]
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
    print 'solo_views.pl_generator: seeds = %s' %(seeds)
    for entry in seeds.items():
        type = entry[0]
        seedslist = list()
        seedslist.append(entry[1]) # avoids missinterpreting one-element lists
        print 'solo_views.pl_generator: type = %s, seedslist = %s' %(type, seedslist)
        if seedslist is not None:
            for seed in seedslist:
                print 'solo_views.pl_generator: seed is "%s" and of type "%s"' %(seed, type)
                if type == 'tags':
                    vect, weight = utils.tag_features(seed)
                    if vect:
                        print 'solo_views.pl_generator: found tag "%s" in the db' %(seed)
                    elif vect is None:
                        print 'solo_views.pl_generator: not found tag "%s" in the db, vect is None' %(seed)
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
                    vect = list()
            tagsmatrix.append(vect)
        
    for i in xrange(len(tagsmatrix[0])):
        vsum = 0
        for tagvect in tagsmatrix: # ugly, find something better, like sympy
            vsum += tagvect[i]
            refvect.append(vsum)
        # TODO normalize
    if refvect is None or not refvect:
        #TODO Handle error
        print 'solo_views.pl_generator: refvect is None'
        raise Exception
    
    # Get options from input
    if options is not None and options:
        print 'solo_views.pl_generator: options = %s' % options
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
        unsorted = default_unrated
    if title is None:
        title = default_title

    
    # Fetch LibEntries
    entries = g.store.find(LibEntry, (LibEntry.user_id == user_id) & LibEntry.is_valid & LibEntry.is_local)
    if not unrated:
        # TODO find if possibility to filter on existing result set entries.
        entrise = g.store.find(LibEntry, (LibEntry.user_id == user_id) & LibEntry.is_valid & LibEntry.is_local & (LibEntry.rating != None) & (LibEntry.rating > 0))
    for entry in entries:
        added = False
        dist=0
        if entry.track.features is not None:
            tagvect = utils.decode_features(entry.track.features)
            dist = fabs(sum([refvect[i] * tagvect[i] for i in range(len(tagvect))]))
            # TODO optimization: filter ASAP, to avoid useless computation
            # Ideal: filter at find() time
            # Filters
            if filter is not None:
                if filter == 'rating>=3' :
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
            prob = 1 - dist  # Associate a probability
            if (size != 'probabilistic') or (size == 'probabilistic' and prob >= random()) :
                probpl.append((entry, prob))
    
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
            # Default 'natural' sorting does nothing
                
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
        pldb = Playlist(user_id, unicode(title), len(playlist), seeds, options, unicode(refvect), tracks) # previously: title='playlist_' + str(randint(0, 99))
        g.store.add(pldb)
        g.store.flush() # See Storm Tutorial: https://storm.canonical.com/Tutorial#Flushing
        print 'solo_views.pl_generator: pldb.id = %s' % pldb.id
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
        
        print 'solo_views.pl_generator: playlistdescriptor = %s' % playlistdescriptor
        return playlistdescriptor
    return None

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
          'gs_creation_time': pllibentry.playlist.created.replace(microsecond=0).isoformat(),
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