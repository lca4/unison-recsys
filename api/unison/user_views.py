#!/usr/bin/env python
"""User-related views."""

import helpers
import libunison.password as password
import libunison.mail as mail
import storm.exceptions
import math
import operator
import random
import json

from constants import errors, events
from flask import Blueprint, request, g, jsonify
from libunison.models import User, UserTags, Group, Track, LibEntry, GroupEvent


user_views = Blueprint('user_views', __name__)

# @author: Hieu
def valid_tracks(user):
    track_ids = list()
    rows = g.store.find(LibEntry, (LibEntry.user == user) 
                        & LibEntry.is_valid)
    for entry in rows:
        track_ids.append(entry.track_id)
    return list(set(track_ids))


# @author: Hieu
def favorite_tags(uid):
    choices = list()
    res = list()
    
    usertags = g.store.get(UserTags, uid)

    if usertags is None:
        track_ids = valid_tracks(uid)
        tag_dict = dict()
        numDoc = 0
        # res.append(not track_ids)
        if track_ids:
            for id in track_ids:
                track = g.store.get(Track, id)
                if track is not None:
                    for tag in eval(track.tags):
                        tag_dict[tag[0]]=tag_dict.get(tag[0],[0.0, 0.0, 0.0])
                        l=tag_dict[tag[0]]
                        l[1] += tag[1] # term frequency
                        l[2] += 1      # number of document that the tag occurs
                    numDoc += 1
            
            for k, v in tag_dict.items():
                if v[1]<10 and v[2]<2:
                    del tag_dict[k]
                else:            
                    v[0] = v[1]*math.log(numDoc/float(v[2])) #another tf-idf
        
            count = 0
            for k in sorted(tag_dict.iteritems(), key=operator.itemgetter(1), reverse=True):
                res.append([k[0],k[1][0],k[1][2]])
                count += 1
                if count > 10:
                    break
            tagjson = json.dumps(res)
            usertags = UserTags(uid,tagjson)
            g.store.add(usertags)
            g.store.flush()
    else:
        res=eval(usertags.tags)
    
    if res:
        sumScore = sum([x[1]/x[2] for x in res])
        while len(choices)<2:
              for t in res:
                  if t[0] not in choices:
                      if random.random()<(t[1]/t[2])/sumScore:
                          choices.append(t[0])
                          if len(choices)>=2:
                              break
    return choices


# @author: Hieu
@user_views.route('/<int:uid>/tags', methods=['GET'])
@helpers.authenticate()
def get_user_tags(uid):
    """Get user's favorite tags"""
    user = g.store.get(User, uid)
    if user is None:
        raise helpers.BadRequest(errors.INVALID_USER,
                "user does not exist")
    tags = favorite_tags(uid)
    return jsonify(tags=tags)


@user_views.route('', methods=['POST'])
def register_user():
    """Register a new user."""
    try:
        email = request.form['email']
        pw = request.form['password']
    except KeyError:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "missing e-mail and / or password")
    # Check that there is no user with that e-mail address.
    if g.store.find(User, User.email == email).one() is not None:
        raise helpers.BadRequest(errors.EXISTING_USER,
                "user already exists")
    # Check that the e-mail address is valid.
    elif not mail.is_valid(email):
        raise helpers.BadRequest(errors.INVALID_EMAIL,
                "e-mail is not valid")
    # Check that the password is good enough.
    elif not password.is_good_enough(pw):
        raise helpers.BadRequest(errors.INVALID_PASSWORD,
                "password is not satisfactory")
    # All the checks went through, we can create the user.
    user = User(email, password.encrypt(pw))
    g.store.add(user)
    g.store.flush()  # Necessary to get an ID.
    # Default nickname.
    user.nickname = unicode("user%d" % user.id)
    return jsonify(uid=user.id)


@user_views.route('/<int:uid>/nickname', methods=['GET'])
@helpers.authenticate()
def get_user_nickname(uid):
    """Get any user's nickname."""
    user = g.store.get(User, uid)
    if user is None:
        raise helpers.BadRequest(errors.INVALID_USER,
                "user does not exist")
    return jsonify(uid=user.id, nickname=user.nickname)


@user_views.route('/<int:uid>/nickname', methods=['PUT'])
@helpers.authenticate(with_user=True)
def update_user_nickname(user, uid):
    """Assign a nickname to the user."""
    helpers.ensure_users_match(user, uid)
    try:
        user.nickname = request.form['nickname']
    except KeyError:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "missing nickname")
    return helpers.success()


@user_views.route('/<int:uid>/email', methods=['PUT'])
@helpers.authenticate(with_user=True)
def update_user_email(user, uid):
    """Update the user's e-mail address."""
    helpers.ensure_users_match(user, uid)
    try:
        email = request.form['email']
    except KeyError:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "missing e-mail address")
    if not mail.is_valid(email):
        raise helpers.BadRequest(errors.INVALID_EMAIL,
                "e-mail is not valid")
    try:
        user.email = email
        g.store.flush()
    except storm.exceptions.IntegrityError:
        # E-mail already in database.
        raise helpers.BadRequest(errors.EXISTING_USER,
                "e-mail already taken by another user")
    return helpers.success()


@user_views.route('/<int:uid>/password', methods=['PUT'])
@helpers.authenticate(with_user=True)
def update_user_password(user, uid):
    """Update the user's password."""
    helpers.ensure_users_match(user, uid)
    try:
        pw = request.form['password']
    except KeyError:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "missing password")
    if not password.is_good_enough(pw):
        raise helpers.BadRequest(errors.INVALID_EMAIL,
                "password is not satisfactory")
    user.password = password.encrypt(pw)
    return helpers.success()


@user_views.route('/<int:uid>/group', methods=['PUT', 'DELETE'])
@helpers.authenticate(with_user=True)
def update_user_group(user, uid):
    """Join or leave a group."""
    helpers.ensure_users_match(user, uid)
    if request.method == 'DELETE':
        if user.group is not None:
            if user.group.master == user:
                user.group.master = None
            event = GroupEvent(user.group, user, events.LEAVE, None)
            g.store.add(event)
        user.group = None
        return helpers.success()
    try:
        gid = int(request.form['gid'])
    except:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "cannot to parse group ID")
    group = g.store.get(Group, gid)
    if group is None:
        raise helpers.BadRequest(errors.INVALID_GROUP,
                "group does not exist")
    if group.password is not None:
        try:
            password = request.form['password']
            
        except:
            raise helpers.BadRequest(errors.PASSWORD_EXPECTED,
                    "password expected")
        if password != group.password:
            raise helpers.Forbidden("received an invalid group password")
            
    if user.group != group:
        if user.group is not None:
            if user.group.master == user:
                # The user was his old group's master.
                user.group.master == None
            event = GroupEvent(user.group, user, events.LEAVE, None)
            g.store.add(event)
        user.group = group
        event = GroupEvent(group, user, events.JOIN, None)
        g.store.add(event)
    return helpers.success()
