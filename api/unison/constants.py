#!/usr/bin/env python
"""Constants used by the API."""


class Namespace(object):
    """Dummy class used to namespace constants."""
    pass


# API errors.
errors = Namespace()
errors.MISSING_FIELD = 0x01
errors.EXISTING_USER = 0x02
errors.INVALID_USER = 0x12
errors.INVALID_RATING = 0x03
errors.INVALID_EMAIL = 0x04
errors.INVALID_PASSWORD = 0x05
errors.INVALID_GROUP = 0x06
errors.INVALID_TRACK = 0x07
errors.INVALID_LIBENTRY = 0x08
errors.INVALID_DELTA = 0x09
errors.UNAUTHORIZED = 0x0a
errors.TRACKS_DEPLETED = 0x0b
errors.MASTER_TAKEN = 0x0c
errors.NO_CURRENT_TRACK = 0x0d
#Added by Vincent:
errors.MISSING_CLUSTER = 0x0e
errors.FORBIDDEN = 0x0f
errors.PASSWORD_EXPECTED= 0x10
#Added by Marc:
errors.IS_EMPTY = 0x20
errors.OPERATION_FAILED = 0x21
errors.NO_TAGGED_TRACKS = 0x22

# Group events.
events = Namespace()
events.RATING = u'rating'
events.JOIN = u'join'
events.LEAVE = u'leave'
events.PLAY = u'play'
events.SKIP = u'skip'
events.MASTER = u'master'
