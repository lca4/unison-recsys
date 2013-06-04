#!/usr/bin/env python

import numpy as np
import sklearn.mixture
import utils
import math
import pickle

from operator import itemgetter, mul
from models import *


DIMENSIONS = 5
SCALE = 5


class Model(object):

    K_MAX = 10
    MIN_COVAR = 0.001

    def __init__(self, user):
        self._user = user
        if user.model is not None:
            self._gmm = pickle.loads(user.model.encode('utf-8'))
        else:
            self._gmm = None

    def generate(self, store):
        points = get_points(self._user, store)
        k_max = min(self.K_MAX, len(points) / (2 * DIMENSIONS))
        if k_max < 1:
            self._user.model = None
            self._gmm = None
            return
        candidates = list()
        for k in range(1, k_max+1):
            gmm = sklearn.mixture.GMM(n_components=k, covariance_type='full',
                    min_covar=self.MIN_COVAR)
            gmm.fit(points)
            candidates.append((gmm, gmm.bic(points)))
        self._gmm, bic = min(candidates, key=itemgetter(1))
        self._user.model = unicode(pickle.dumps(self._gmm))
        store.flush()

    def is_nontrivial(self):
        return self._gmm is not None

    def get_nb_components(self):
        if not self.is_nontrivial():
            return 0
        return self._gmm.n_components

    def score(self, points):
        if not self.is_nontrivial():
            return None
        return [math.exp(x) for x in self._gmm.score(points)]


def get_points(user, store):
    points = list()
    rows = store.find(LibEntry, (LibEntry.user == user)
            & LibEntry.is_local & LibEntry.is_valid)
    for row in rows:
        point = get_point(row.track)
        if point is not None:
            points.append(point)
    return np.array(points)


def get_point(track):
    if track.features is not None:
        features = utils.decode_features(track.features)
        return [x*SCALE for x in features[:DIMENSIONS]]
    return None


def aggregate(ratings, mode='mult'):
    aggregate = list()
    for track_ratings in zip(*ratings):
        if mode == 'mult':
            track_aggregate = reduce(mul, track_ratings)
        elif mode == 'add':
            track_aggregate = sum(track_ratings)
        else:
            raise ValueError('mode unknown')
        aggregate.append(track_aggregate)
    return aggregate

#@author: Hieu
def get_tag_point(tag):
    features,weight = utils.tag_features(tag, None, False)
    return [x*SCALE for x in features[:DIMENSIONS]]

def score_by_tag(tag_features, track_features):
    return sum(map(mul, tag_features, track_features))

# borda rank by sum of rank
def bordarank(ranked_ratings, length):
    mm = dict()
    for i in range(0,length):
        for r in ranked_ratings:
            mm[r[i]] = mm.get(r[i],0)+i
    return [entry for entry,score in sorted(mapp.items(),key=itemgetter(1), reverse=False)]

# calculate the transition matrix base on borda rank (small trick)
def transition_matrix(ranked_list_desc):
    length = len(ranked_list_desc)
    p = np.matrix(np.zeros((length,length)))
    for i in range(0,length-1):
        for j in range(i,length):
            p[ranked_list_desc[i],ranked_list_desc[j]]=1.0/length;
    sub = np.ones((length,1))-p.sum(axis=1)
    for i in range(0,length):
        p[i,i]=sub[i,0]
    return p

# return stationary probabilities of markov chain
def markovchain4(p):
    S,U = eig(p.T)
    stationary = np.array(U[:,np.where(np.abs(S-1.) < 1e-8)[0][0]].flat)
    stationary = stationary / np.sum(stationary)
    return stationary

#end @author: Hieu

