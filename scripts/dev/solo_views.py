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


@solo_views.route('/<int:gid>/playlist', methods=['GET'])
@helpers.authenticate(with_user=True)
def get_playlist(gid):
    """Get a playlist"""
    type = request.form['type']
    seed = request.form['seed']
    filter = request.form['filter']
    size = request.form['size']
    sort = request.form['sort']
    
    if type is None:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "type of seed not specified")
    elif seed is None:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "seed not specified")
    
    playlist = plgenerator.plgenerator(gid, type, seed, filter, size, sort)
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