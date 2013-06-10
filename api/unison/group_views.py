#!/usr/bin/env python
"""Group-related views."""

import datetime
import hashlib
import helpers
import libunison.geometry as geometry
import libunison.predict as predict
import random
import time
import re
import math

from constants import errors, events
from flask import Blueprint, request, g, jsonify
from libentry_views import set_rating
from libunison.models import User, UserTags, Group, Track, LibEntry, GroupEvent, Cluster
from operator import itemgetter
from storm.expr import Desc, In
from storm.locals import AutoReload

# Maximal number of groups returned when listing groups.
MAX_GROUPS = 10

# Maximal number of tracks returned when asking for the next tracks.
MAX_TRACKS = 5

# Interval during which we don't play the same song again.
ACTIVITY_INTERVAL = 60 * 60 * 5  # In seconds.

# Minimum size of a cluster so that we make a suggestion.
MIN_SUGGESTION_SIZE = 2

#number of users of a newly created group, for now the group is created empty.
NB_USERS_IN_NEW_GROUP = 0

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
    rows = sorted(g.store.find(Group, (Group.is_active) & (Group.is_automatic == False)), key=key_fct) # "not" doesn't work...
    for group in rows[:MAX_GROUPS]:
        groups.append({
          'gid': group.id,
          'name': group.name,
          'nb_users': group.users.count(),
          'distance': (geometry.distance(userloc, group.coordinates)
                  if userloc is not None else None),
    		  'password': group.password != None
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
    #Added by Vincent:
    
    group = Group(name, is_active=True)
    group.coordinates = geometry.Point(lat, lon)
    group = g.store.add(group)
    
    
    askList = False
    if 'list' in request.form:
        askList = bool(request.form['list'])
      
    if askList:
        return list_groups()
    else:
        #the user asked only for the newly created group to be returned.
        group.id = AutoReload
        groupDict = {
          'gid': group.id,
          'name': group.name,
          'nb_users': NB_USERS_IN_NEW_GROUP, #the group has just been created
          'distance': 0.0, #this won't be displayed anyway
#          'distance': (geometry.distance(userloc, group.coordinates)
#                if userloc is not None else None), #this should be either 0 or None
          'password': False #the group has just been created
        }
        #TODO: understand why we cannot give the json object a name
        return jsonify(groupDict)


#Added by Louis for group password handling	
@group_views.route('/<int:gid>', methods=['PUT'])
@helpers.authenticate(with_user=True)
def put_new_password(user, gid):
    """Change the password for the group or sets one if there is one.
	
    We must decide if the users already in the group should be prompted for the new password.
	
    """
	
    try:
        password = request.form['password']
    except (KeyrError, ValueError):
        raise helpers.BadRequest(errors.MISSING_FIELD,
            "group password is missing")
    group = g.store.get(Group, gid)

    if group is None:
        raise helpers.BadRequest(errors.INVALID_GROUP,
            "group does not exist")

    if user.id != group.master_id or group.is_automatic:
        raise helpers.BadRequest(errors.UNAUTHORIZED,
            "not allowed to change group password unless DJ")
	
    group.password = password if (password != '') else None
	#event = GroupEvent(user, user, events.PASSWORD, password)
	#TODO check if this is correct
	#g.store.add(event)
	
    return helpers.success()


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
    if not remaining: # http://stackoverflow.com/questions/53513/python-what-is-the-best-way-to-check-if-a-list-is-empty
        # Instead of removing the read tracks, reload all the tracks
        remaining = g.store.find(LibEntry,
            (LibEntry.user == master) & (LibEntry.is_valid == True)
            & (LibEntry.is_local == True))
        if not remaining:
            raise helpers.NotFound(errors.TRACKS_DEPLETED, 'no tracks to play')
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

    #@author: Hieu
    # Get users' current preferences
    pref_users = [user.id for user in group.users if user is not None]
    prefs = [usertags.preference for usertags in [g.store.get(UserTags,u) for u in pref_users] if usertags is not None and usertags.preference]
    prefs_features = [predict.get_tag_point(tag) for tag in prefs]
    
    # The effect of current preferences 
    # calculate sum of dot products of every point with every tag/pref and group by point
    prefs_ratings_agg = [sum([predict.score_by_tag(ppoint,ppref) for ppref in prefs_features if ppref is not None]) for ppoint in points]
    
    # construct the playlist, decreasing order of preference scores
    playlist_by_pref = [entry for entry, score in sorted(
            zip(with_feats, prefs_ratings_agg), key=itemgetter(1), reverse=True)]
    
    # For the users that can be modelled: predict their ratings.
    models = filter(lambda model: model.is_nontrivial(),
            [predict.Model(user) for user in group.users])
    playlist_model = list()
    
    if len(models) > 0:
        ratings = [model.score(points) for model in models]
        # obsoleted
        agg = predict.aggregate(ratings)
        #mindex = [i for i in range(0,len(points))]
        #ranked_ratings = [[entry for entry, score in sorted(zip(mindex,r), key=itemgetter(1), reverse=True)] for r in ratings]
        #
        ##inverse_borda: list of ascending preferences
        #inverse_borda = predict.inverse_borda_rank(ranked_ratings, len(mindex))
        #final_rank = list()
        #tmp_inverse_borda = inverse_borda
        #iter = 0
        #stop = False
        #while not stop and iter<10000:
        #    transition_matrix = predict.transition_matrix(inverse_borda)
        #    stationary = predict.markovchain4(transition_matrix)
        #    addition = [entry for entry, score in sorted(zip(tmp_inverse_borda, stationary), key=itemgetter(1), reverse=True) if score>0]
        #    final_rank = final_rank+addition
        #    tmp_inverse_borda = [x for x in tmp_inverse_borda if x not in addition]
        #    if not tmp_inverse_borda:
        #        stop = True
        #    iter = iter+1
        #if len(final_rank) < len(points):
        #    final_rank = final_rank + tmp_inverse_borda
        #playlist_model = [with_feats[i] for i in final_rank]
    else:
        # Not a single user can be modelled! just order the songs randomly.
        agg = range(len(with_feats))
        random.shuffle(agg)
        # Construct the playlist, decreasing order of scores.
        playlist_model = [entry for entry, score in sorted(zip(with_feats, agg), key=itemgetter(1), reverse=True)]
    
    #@author: Hieu
    # merge two playlists of preferences and models
    entry_dict = dict()
    weight = [0.75, 0.25]; #weight(preference,models)
    
    for i in range (0,len(playlist_model)):
        entry_dict[playlist_model[i]] = weight[1]*(i+1)
    for i in range (0,len(playlist_by_pref)):
        entry_dict[playlist_by_pref[i]] += weight[0]*(i+1)
    
    playlist = [k[0] for k in sorted(entry_dict.iteritems(), key=itemgetter(1), reverse=False)]
    
    #@end-author: Hieu 

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
        lat = float(request.args['lat'])
        lon = float(request.args['lon'])
    except (KeyError, ValueError):
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "cannot parse lat and lon")

    #TODO: only remove and add if necessary
    

    # Get user's location to put him in a cluster.
    user_loc = geometry.Point(lat, lon)
    cluster_loc = geometry.map_location_on_grid(user_loc)
    clusterRequest = g.store.execute("SELECT * FROM \"cluster\" WHERE position ~= CAST ('("+str(cluster_loc.lat)+","+str(cluster_loc.lon)+")' AS point)")
    clusterResult = clusterRequest.get_one()
    clusterRequest.close() # close the cursor in DB


    if clusterResult is None:
        cluster = Cluster(cluster_loc)
        cluster = g.store.add(cluster)
        cluster.id = AutoReload
    else:
        coordinatesList = re.split('[\(,\)]', clusterResult[1])
    #CAUTION: format is ('', 'lat', 'lon', '')
#    cluster = Cluster(geometry.Point(float(coordinatesList[1]), float(coordinatesList[2])))
#    cluster.id = clusterResult[0]
#    cluster.group_id = clusterResult[2]

        #now we get the cluster by its ID because otherwise the store doesn't seem to be properly set for this cluster
        cluster = g.store.get(Cluster, clusterResult[0] )

    
    user.cluster_id = cluster.id
#    usersInCluster = g.store.find(User, (User.cluster_id == cluster.id))
    usersInCluster = cluster.users
    size = usersInCluster.count()
    if size < MIN_SUGGESTION_SIZE:
        return jsonify(suggestion=False, clusterId=cluster.id)
    else:
        #Create group for cluster if needed:
        if cluster.group_id is None:
            groupName = u''
            clusterGroup = Group(groupName, is_active=True)
            clusterGroup.is_automatic = True
            #We need some values added by the database, like the ID.
            clusterGroup = g.store.add(clusterGroup)
            clusterGroup.coordinates = geometry.Point(cluster_loc.lat, cluster_loc.lon) #this value cannot be null when inserted into the DB
            clusterGroup.id = AutoReload
            clusterGroup.name = u'AutoGroup ' + str(clusterGroup.id) #result type is "unicode"
            #tie the group with the cluster
            cluster.group_id = clusterGroup.id
        else:
            clusterGroup = g.store.get(Group, cluster.group_id)
        #Retrieve users already in cluster:
        users = list()
        for user in usersInCluster:
            users.append(user.nickname)

        #Create a dictionary representing the group as in list_groups: TODO: modularize
        groupDict = {
          'gid': clusterGroup.id,
          'name': clusterGroup.name,
          'nb_users': clusterGroup.users.count(),
          'distance': None,
          'lat': clusterGroup.coordinates.lat,
          'lon': clusterGroup.coordinates.lon,
          'automatic': True
        }
        #Create a dictionary representing the cluster:
        clusterDict = {
                        'cid': cluster.id,
                        'lat': cluster.coordinates.lat,
                        'lon': cluster.coordinates.lon,
                        'gid': cluster.group_id
                      }
        return jsonify(suggestion=True, cluster=clusterDict, group=groupDict, users=users)

