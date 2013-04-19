#!/usr/bin/env python
"""Group-related views."""

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
#added by vincent, should be needed  after bug fix:
from math import floor, fabs


# Maximal number of groups returned when listing groups.
MAX_GROUPS = 10

# Maximal number of tracks returned when asking for the next tracks.
MAX_TRACKS = 5

# Interval during which we don't play the same song again.
ACTIVITY_INTERVAL = 60 * 60 * 5  # In seconds.

# Minimum size of a cluster so that we make a suggestion.
MIN_SUGGESTION_SIZE = 2

#Added by vincent, should be removed after bug fix:
LAT_THRESHOLD = 30 # seconds
LON_THRESHOLD = 60 # seconds

group_views = Blueprint('group_views', __name__)


@group_views.route('', methods=['GET'])
@helpers.authenticate()
def list_groups():
    """Get a list of groups."""
    userloc = None
    try:
        lat = float(request.values['lat'])
        lon = float(request.values['lon'])
    except (KeyError, ValueError):
        # Sort by descending ID - new groups come first.
        key_fct = lambda r: -1 * r.id
    else:
        # Sort the rows according to the distance from the user's location.
        userloc = geometry.Point(lat, lon)
        key_fct = lambda r: geometry.distance(userloc, r.coordinates)
    groups = list()
    rows = sorted(g.store.find(Group, Group.is_active), key=key_fct)
    for group in rows[:MAX_GROUPS]:
        groups.append({
          'gid': group.id,
          'name': group.name,
          'nb_users': group.users.count(),
          'distance': (geometry.distance(userloc, group.coordinates)
                  if userloc is not None else None),
        })
    return jsonify(groups=groups)


@group_views.route('', methods=['POST'])
@helpers.authenticate()
def create_group():
    """Create a new group."""
    try:
        name = request.form['name']
        lat = float(request.form['lat'])
        lon = float(request.form['lon'])
    except (KeyError, ValueError):
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "group name, latitude or longitude is missing or invalid")
    group = Group(name, is_active=True)
    group.coordinates = geometry.Point(lat, lon)
    g.store.add(group)
    return list_groups()


@group_views.route('/<int:gid>', methods=['GET'])
@helpers.authenticate()
def get_group_info(gid):
    """Get infos about the specified group.

    Includes:
    - participants in the group (ID, nickname & stats)
    - current DJ (ID & nickname)
    - info about last track
    """
    group = g.store.get(Group, gid)
    if group is None:
        raise helpers.BadRequest(errors.INVALID_GROUP,
                "group does not exist")
    userdict = dict()
    for user in group.users:
        userdict[user.id] = {'nickname': user.nickname}
    # Search for the last track that was played.
    results = g.store.find(GroupEvent, (GroupEvent.event_type == events.PLAY)
            & (GroupEvent.group == group))
    track = None
    play_event = results.order_by(Desc(GroupEvent.created)).first()
    if play_event is not None:
        artist = play_event.payload.get('artist')
        title = play_event.payload.get('title')
        row = g.store.find(Track, (Track.artist == artist)
                & (Track.title == title)).one()
        image = row.image if row is not None else None
        track = {
          'artist': artist,
          'title': title,
          'image': image,
        }
        for entry in play_event.payload.get('stats', []):
            if entry.get('uid') in userdict:
                uid = entry['uid']
                userdict[uid]['score'] = entry.get('score')
                userdict[uid]['predicted'] = entry.get('predicted', True)
    users = list()
    for key, val in userdict.iteritems():
        users.append({
          'uid': key,
          'nickname': val.get('nickname'),
          'score': val.get('score'),
          'predicted': val.get('predicted', True)
        })
    master = None
    if group.master is not None:
        master = {
          'uid': group.master.id,
          'nickname': group.master.nickname
        }
    return jsonify(name=group.name, track=track, master=master, users=users)


def get_played_filter(group):
    played = set()
    threshold = datetime.datetime.fromtimestamp(
            time.time() - ACTIVITY_INTERVAL)
    events = g.store.find(GroupEvent, (GroupEvent.group == group)
        & (GroupEvent.event_type == u'play') & (GroupEvent.created > threshold))
    for event in events:
        info = (event.payload.get('artist'), event.payload.get('title'))
        played.add(info)
    def played_filter(entry):
        info = (entry.track.artist, entry.track.title)
        return info not in played
    return played_filter


def get_playlist_id(group):
    # Find last event in the group that could have changed the playlist
    events = g.store.find(GroupEvent, (GroupEvent.group == group)
            & In(GroupEvent.event_type, [u'join', u'leave', u'master']))
    last = events.order_by(Desc(GroupEvent.created)).first()
    if last is not None:
        when = last.created
    else:
        when = datetime.datetime.utcnow()
    return unicode(hashlib.sha1(when.strftime('%s')).hexdigest())


@group_views.route('/<int:gid>/playlist', methods=['GET'])
@helpers.authenticate(with_user=True)
def get_playlist(master, gid):
    """Get the playlist id."""
    group = g.store.get(Group, gid)
    if group is None:
        raise helpers.BadRequest(errors.INVALID_GROUP,
                "group does not exist")
    id = get_playlist_id(group)
    return jsonify(playlist_id=id)


@group_views.route('/<int:gid>/tracks', methods=['GET'])
@helpers.authenticate(with_user=True)
def get_tracks(master, gid):
    """Get the next tracks."""
    group = g.store.get(Group, gid)
    if group is None:
        raise helpers.BadRequest(errors.INVALID_GROUP,
                "group does not exist")
    if group.master != master:
        raise helpers.Unauthorized("you are not the DJ")
    # Get all the tracks in the master's library that haven't been played.
    played_filter = get_played_filter(group)
    remaining = filter(played_filter, g.store.find(LibEntry,
            (LibEntry.user == master) & (LibEntry.is_valid == True)
            & (LibEntry.is_local == True)))
    if len(remaining) == 0:
        raise helpers.NotFound(errors.TRACKS_DEPLETED,
                'no more tracks to play')
    # Partition tracks based on whether we can embed them in the latent space.
    with_feats = list()
    points = list()
    no_feats = list()
    for entry in remaining:
        point = predict.get_point(entry.track)
        if point is not None:
            with_feats.append(entry)
            points.append(point)
        else:
            no_feats.append(entry)
    # For the users that can be modelled: predict their ratings.
    models = filter(lambda model: model.is_nontrivial(),
            [predict.Model(user) for user in group.users])
    if len(models) > 0:
        ratings = [model.score(points) for model in models]
        agg = predict.aggregate(ratings)
    else:
        # Not a single user can be modelled! just order the songs randomly.
        agg = range(len(with_feats))
        random.shuffle(agg)
    # Construct the playlist, decreasing order of scores.
    playlist = [entry for entry, score in sorted(
            zip(with_feats, agg), key=itemgetter(1), reverse=True)]
    # Randomize songs for which we don't have features.
    random.shuffle(no_feats)
    playlist.extend(no_feats)
    # Craft the JSON response.
    tracks = list()
    for entry in playlist[:MAX_TRACKS]:
        tracks.append({
          'artist': entry.track.artist,
          'title': entry.track.title,
          'local_id': entry.local_id,
        })
    return jsonify(playlist_id=get_playlist_id(group), tracks=tracks)


@group_views.route('/<int:gid>/current', methods=['PUT'])
@helpers.authenticate(with_user=True)
def play_track(user, gid):
    """Register the track that is currently playing."""
    group = g.store.get(Group, gid)
    if group is None:
        raise helpers.BadRequest(errors.INVALID_GROUP,
                "group does not exist")
    if group.master != user:
        raise helpers.Unauthorized("you are not the master")
    try:
        artist = request.form['artist']
        title = request.form['title']
    except KeyError:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "missing artist and / or title")
    track = g.store.find(Track,
            (Track.artist == artist) & (Track.title == title)).one()
    if track is None:
        raise helpers.BadRequest(errors.INVALID_TRACK,
                "track not found")
    payload = {
      'artist': track.artist,
      'title': track.title,
      'master': {'uid': user.id, 'nickname': user.nickname},
    }
    payload['stats'] = list()
    # TODO Something better than random scores :)
    for resident in group.users:
        payload['stats'].append({
          'uid': resident.id,
          'nickname': resident.nickname,
          'score': int(random.random() * 100),
          'predicted': True #if random.random() > 0.2 else False
        })
    event = GroupEvent(group, user, events.PLAY, payload)
    g.store.add(event)
    return helpers.success()


@group_views.route('/<int:gid>/current', methods=['DELETE'])
@helpers.authenticate(with_user=True)
def skip_track(user, gid):
    """Skip the track that is currently being played."""
    group = g.store.get(Group, gid)
    if group is None:
        raise helpers.BadRequest(errors.INVALID_GROUP,
                "group does not exist")
    if group.master != user:
        raise helpers.Unauthorized("you are not the master")
    results = g.store.find(GroupEvent, (GroupEvent.event_type == events.PLAY)
            & (GroupEvent.group == group))
    play_event = results.order_by(Desc(GroupEvent.created)).first()
    if play_event is None:
        raise helpers.BadRequest(errors.NO_CURRENT_TRACK,
                "no track to skip")
    payload = {
      'artist': play_event.payload.get('artist'),
      'title': play_event.payload.get('title'),
      'master': {'uid': user.id, 'nickname': user.nickname},
    }
    event = GroupEvent(group, user, events.SKIP, payload)
    g.store.add(event)
    return helpers.success()


@group_views.route('/<int:gid>/ratings', methods=['POST'])
@helpers.authenticate(with_user=True)
def add_rating(user, gid):
    """Take the DJ spot (if it is available)."""
    group = g.store.get(Group, gid)
    if group is None:
        raise helpers.BadRequest(errors.INVALID_GROUP,
                "group does not exist")
    try:
        artist = request.form['artist']
        title = request.form['title']
        rating = max(1, min(5, int(request.form['rating'])))
    except KeyError:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "missing artist, title or rating")
    except ValueError:
        raise helpers.BadRequest(errors.INVALID_RATING,
                "rating is invalid")
    if user.group != group:
        raise helpers.Unauthorized("you are not in this group")
    track = g.store.find(Track,
            (Track.artist == artist) & (Track.title == title)).one()
    if track is None:
        raise helpers.BadRequest(errors.INVALID_TRACK,
                "track not found")
    # Add a group event.
    event = GroupEvent(group, user, events.RATING)
    event.payload = {
     'artist': track.artist,
     'title': track.title,
     'rating': rating,
    }
    g.store.add(event)
    # Add a library entry.
    set_rating(user, track.artist, track.title, rating)
    return helpers.success()


@group_views.route('/<int:gid>/master', methods=['PUT'])
@helpers.authenticate(with_user=True)
def set_master(user, gid):
    """Take the DJ spot (if it is available)."""
    group = g.store.get(Group, gid)
    if group is None:
        raise helpers.BadRequest(errors.INVALID_GROUP,
                "group does not exist")
    try:
        uid = int(request.form['uid'])
    except (KeyError, ValueError):
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "cannot parse uid")
    if user.id != uid or user.group != group:
        raise helpers.Unauthorized("user not self or not in group")
    if group.master != None and group.master != user:
        raise helpers.Unauthorized("someone else is already here")
    group.master = user
    event = GroupEvent(group, user, events.MASTER, None)
    g.store.add(event)
    return helpers.success()


@group_views.route('/<int:gid>/master', methods=['DELETE'])
@helpers.authenticate(with_user=True)
def leave_master(user, gid):
    """Leave the DJ spot."""
    group = g.store.get(Group, gid)
    if group is None:
        raise helpers.BadRequest(errors.INVALID_GROUP,
                "group does not exist")
    if group.master != None and group.master != user:
        raise helpers.Unauthorized("you are not the master")
    group.master = None
    return helpers.success()


# added by Vincent and Louis
@group_views.route('/suggestion', methods=['GET'])
@helpers.authenticate(with_user=True)
def send_suggest(user):
    try:
        uid = int(request.args['uid'])
    except (KeyError, ValueError):
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "cannot parse uid")
    try:
        lat = float(request.args['lat'])
        lon = float(request.args['lon'])
    except (KeyError, ValueError):
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "cannot parse lat and lon")

    # Get user's location to put him in a cluster.
    user_loc = geometry.Point(lat, lon)
#    cluster_loc = geometry.map_location_on_grid(user_loc)
    cluster_loc = map_location_on_grid(user_loc)

    #TODO: look whether this cluster already exists
    #   if it does, get the list of users already in this cluster then put the user un this cluster.
    #   otherwise, add him in the cluster and send no suggestion.

    #pseudo code :)
    # psql request on the DB: table clusters: for cluster_loc
#    cluster = g.store.find(Cluster, (Cluster.coordinates == cluster_loc))
#    if cluster is not None:
#        raise helpers.BadRequest(errors.INVALID_TRACK,
#                "we are on the good way!")
#    else:
#        raise helpers.BadRequest(errors.INVALID_TRACK,
#                "we couldn't retrieve the cluster!")


    # if (clusterID is None)
    #   create new cluster entry with cluster_loc in table clusters (the corresponding group will only be created when first user accepts suggestion)
    #   create new cluster_user pair with cluster.id and user.id in table cluster_user
    # else
    #   if cluster.nbr_of_users > MIN_SUGGESTION_SIZE
    #       users_list = cluster.users_list
    #       cluster.users_list.add(user)
    #       return suggestion with users_list
    #   else
    #       cluster.users_list.add(user)

    return helpers.success()


#added by Vincent and Louis. This Shouldn't be here but in geometry lib instead,
#but that way doesn't work for now.
# point is a geometry.Point
def map_location_on_grid(point):
    lat = point.lat
    lon = point.lon

    north = lat > 0
    east = lon > 0
    
    lat = fabs(lat)
    lon = fabs(lon)

    #convert into sexadecimal notation and round
    lat_deg = floor(lat)
    lat = (lat - lat_deg)*60
    lat_min = floor(lat)
    lat = (lat - lat_min)*60
    lat_sec = floor(lat)

    lon_deg = floor(lon)
    lon = (lon - lon_deg)*60
    lon_min = floor(lon)
    lon = (lon - lon_min)*60
    lon_sec = floor(lon)

    #rouding according to threshold:
    if (lat_sec < LAT_THRESHOLD/2):
        lat_sec = 0
    elif (lat_sec < 3*LAT_THRESHOLD/2):
        lat_sec = LAT_THRESHOLD
    else:
        lat_sec = 0
        lat_min += 1

    if (lon_sec > LON_THRESHOLD/2):
        lon_min += 1
    lon_sec = 0

    #get back to decimal notation:
    lat = lat_min + (lat_sec / 60.0)
    lat = lat_deg + (lat / 60.0)

    if not north:
        lat = -lat

    lon = lon_min + (lon_sec / 60.0)
    lon = lon_deg + (lon / 60.0)

    if not east:
        lon = -lon

    return geometry.Point(lat, lon)
