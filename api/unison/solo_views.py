#!/usr/bin/env python
"""Single-user-related views."""


import datetime
import hashlib
import helpers
import libunison.geometry as geometry
import libunison.predict as predict
import random
import time

from constants import errors, events
from flask import Blueprint, request, g, jsonify
from libentry_views import set_rating
from libunison.models import User, Group, Track, LibEntry, GroupEvent
from operator import itemgetter
from storm.expr import Desc, In


group_views = Blueprint('solo_views', __name__)


@solo_views.route('/<int:uid>/playlist', methods=['GET'])
@helpers.authenticate(with_user=True)
def generate_playlist(uid):
    """Get a playlist"""
#     type = request.form['type']
#     seed = request.form['seed']
#     filter = request.form['filter']
#     size = request.form['size']
#     sort = request.form['sort']
    seeds = request.form['seeds']
    options = request.form['options'] # Can be missing
    
    if seeds is None:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "seeds are missing")
    
    playlist = plgenerator.plgenerator(uid, seeds, options)
    # Craft the JSON response.
    if playlist is not None:
        tracks = list()
        for entry in playlist:
            tracks.append({
              'artist': entry.track.artist,
              'title': entry.track.title,
              'local_id': entry.local_id,
            })
        return jsonify(tracks=tracks)
    return None

@solo_views.route('/<int:uid>/playlist', methods=['POST'])
@helpers.authenticate(with_user=True)
def create_playlist(uid):
    #TODO
    raise helpers.BadRequest(errors.MISSING_FIELD,
                "not yet available")
    return None


@solo_views.route('/<int:uid>/playlists/<int:pid>', methods=['GET'])
@helpers.authenticate(with_user=True)
def get_playlist(uid, pid):
    #TODO
    raise helpers.BadRequest(errors.MISSING_FIELD,
                "not yet available")
    return None

# Returns the list of playlists of user uid
@solo_views.route('/<int:uid>/playlists', methods=['GET'])
@helpers.authenticate(with_user=True)
def get_playlists(uid):
    #TODO
    raise helpers.BadRequest(errors.MISSING_FIELD,
                "not yet available")
    return None


# Updates the playlist plid from user uid
@solo_views.route('/<int:uid>/playlists/<int:plid>', methods=['POST'])
@helpers.authenticate(with_user=True)
def update_playlist(uid, plid):
    #TODO
    raise helpers.BadRequest(errors.MISSING_FIELD,
                "not yet available")
    return None


# Disables the playlist plid from user uid
@solo_views.route('/<int:uid>/playlists/<int:plid>', methods=['POST'])
@helpers.authenticate(with_user=True)
def remove_playlist(uid, plid):
    #TODO
    raise helpers.BadRequest(errors.MISSING_FIELD,
                "not yet available")
    return None

