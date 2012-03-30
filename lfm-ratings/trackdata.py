#!/usr/bin/env python

import argparse
import json
import sqlite3
import sys
import urllib
import urllib2
import time


DEFAULT_KEY_FILE = '../lastfm.key'
DEFAULT_IN_DATABASE = 'gen/userdata.db'
DEFAULT_OUT_DATABASE = 'gen/trackdata.db'
API_ROOT = 'http://ws.audioscrobbler.com/2.0/'

DB_SCHEMA = """
    CREATE TABLE IF NOT EXISTS tracks(
      artist TEXT,
      title TEXT,
      tags TEXT,
      features TEXT
    );
    CREATE INDEX IF NOT EXISTS tracks_idx ON tracks(artist, title);
    """

QUERY_TRACK_EXISTS = 'SELECT 1 FROM tracks WHERE artist = ? AND title = ?'
QUERY_INSERT_TRACK = 'INSERT INTO tracks (artist, title, tags) VALUES (?, ?, ?)'

# 'in' database queries.
QUERY_GET_USER = 'SELECT ROWID FROM users WHERE name = ?'
QUERY_GET_TRACKS = 'SELECT artist, title FROM tracks WHERE user = ?'


def process(artist, title, db_conn, api_key):
    res = out_conn.execute(QUERY_TRACK_EXISTS, (artist, title)).fetchone()
    if res is not None:
        # Track is already in database.
        sys.stdout.write("-")
        sys.stdout.flush()
        return
    # Track not in database. We have to fetch the tags.
    time.sleep(1)
    res = lastfm_toptags(artist, title, api_key)
    if 'toptags' not in res:
        raise ValueError("last.fm says '%s'" % res.get('message'))
    toptags = res['toptags'].get('tag', [])
    # When there is a single tag, last.fm doesn't wrap it in an array.
    if type(toptags) is dict:
        toptags = [toptags]
    # Reformat and insert the metadata in the database.
    tags = json.dumps([[tag['name'], tag['count']] for tag in toptags])
    db_conn.execute(QUERY_INSERT_TRACK, (artist, title, tags))
    db_conn.commit()
    sys.stdout.write(".")
    sys.stdout.flush()


def lastfm_toptags(artist, title, api_key):
    params = {
      'format'     : 'json',
      'api_key'    : api_key,
      'method'     : 'track.gettoptags',
      'autocorrect': '1',
      'artist'     : artist.encode('utf-8'),
      'track'      : title.encode('utf-8')
    }
    query_str = urllib.urlencode(params)
    res = urllib2.urlopen(API_ROOT, query_str).read()
    return json.loads(res)


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', default=DEFAULT_KEY_FILE)
    parser.add_argument('--in-db', default=DEFAULT_IN_DATABASE)
    parser.add_argument('--out-db', default=DEFAULT_OUT_DATABASE)
    parser.add_argument('users')
    return parser.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    api_key = open(args.key).read().strip()
    # Setup input DB
    in_conn = sqlite3.connect(args.in_db)
    # Setup output DB.
    out_conn = sqlite3.connect(args.out_db)
    out_conn.executescript(DB_SCHEMA)
    for line in open(args.users):
        user = line.strip()
        print "processing user '%s'" % user
        res = in_conn.execute(QUERY_GET_USER, (user,)).fetchone()
        if res is None:
            print "user not found."
            continue
        uid = res[0]
        for row in in_conn.execute(QUERY_GET_TRACKS, (uid,)).fetchall():
            try:
                process(row[0], row[1], out_conn, api_key)
            except Exception as e:
                print "problem while processing (%s, %s): %s" % (
                        row[0], row[1], e)
        print ''
