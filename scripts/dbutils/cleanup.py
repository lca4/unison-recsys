#!/usr/bin/env python
import argparse
import datetime
import time
import libunison.utils as uutils

from libunison.models import User, GroupEvent, Group
from storm.locals import *
from storm.expr import Desc


def cleanup(interval, verbose, is_dry_run):
    thresh = datetime.datetime.fromtimestamp(
            time.time() - interval * 60 * 60)
    store = uutils.get_store()
    count = 0
    for group in store.find(Group, Group.is_active == True):
        # Iterate over all active groups.
        last_event = store.find(GroupEvent, GroupEvent.group
                == group).order_by(Desc(GroupEvent.created)).first()
        if (last_event is None and group.created < thresh
                or last_event is not None and last_event.created < thresh):
            # Group is old and has no event, or last event is old.
            count += 1
            if verbose:
                print "deactivating group %d (%s)" % (group.id, group.name)
            if not is_dry_run:
                group.is_active = False
                if group.is_automatic:
                    for cluster in group.clusters:
                        # There should be only one cluster.
                        cluster.group = None
                for user in group.users:
                    user.group = None
    store.commit()
    return count


def _parse_args():
    parser = argparse.ArgumentParser()
    # Cutoff interval, number of hours since last event in group.
    parser.add_argument('interval', type=int)
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    return parser.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    count = cleanup(args.interval, args.verbose, args.dry_run)
    now = time.strftime("%a %d %b %y %H:%M:%S")
    print "%s - cleaned up %d groups" % (now, count)
