#!/usr/bin/env python
"""Main API controller."""

import helpers
import libunison.mail as mail
import time
import yaml

from flask import Flask, request, g, Response, jsonify
from libunison.models import User
from storm.locals import create_database, Store

# Blueprints.
from user_views import user_views
from group_views import group_views
from libentry_views import libentry_views
from solo_views import solo_views


PASSWORD_RESET_URL = ("http://staging.groupstreamer.com/"
        "resetpw?uid=%d&ts=%d&mac=%s")


app = Flask(__name__)
app.register_blueprint(user_views, url_prefix='/users')
app.register_blueprint(group_views, url_prefix='/groups')
app.register_blueprint(libentry_views, url_prefix='/libentries')
app.register_blueprint(solo_views, url_prefix='/solo')


@app.before_request
def setup_request():
    # Read the configuration.
    stream = open('%s/config.yaml' % request.environ['UNISON_ROOT'])
    g.config = yaml.load(stream)
    # Set up the database.
    database = create_database(g.config['database']['string'])
    g.store = Store(database)


@app.after_request
def teardown_request(response):
    # Commit & close the database connection.
    g.store.commit()
    g.store.close()
    return response


@app.errorhandler(401)
def handle_unauthorized(error):
    if isinstance(error, helpers.Unauthorized):
        response = jsonify(error=error.error, message=error.msg)
        response.status_code = 401
        response.headers = {'WWW-Authenticate': 'Basic realm="API Access"'}
        return response
    return "unauthorized", 401


@app.errorhandler(400)
def handle_bad_request(error):
    if isinstance(error, helpers.BadRequest):
        response = jsonify(error=error.error, message=error.msg)
        response.status_code = 400
        return response
    return "bad request", 400


@app.errorhandler(404)
def handle_not_found(error):
    if isinstance(error, helpers.NotFound):
        response = jsonify(error=error.error, message=error.msg)
        response.status_code = 404
        return response
    return "not found", 404


@app.errorhandler(403)
def handle_forbidden(error):
    if (isinstance(error, helpers.Forbidden)):
        response = jsonify(error=error.error, message=error.msg)
        response.status_code = 403
        return response
    return "forbidden", 403


@app.route('/')
@helpers.authenticate(with_user=True)
def root(user):
    """Root of the API.

    A call to this resource might be used to test the login credentials and
    retriever basic information about the user. Not very RESTful, but pretty
    useful :)
    """
    return jsonify(uid=user.id, nickname=user.nickname, gid=user.group_id)


@app.route('resetpw', methods=['POST'])
def reset_password():
    """Send an e-mail containing a link to reset the password."""
    try:
        email = request.form['email']
    except KeyError:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "missing e-mail address")
    user = g.store.find(User, User.email == email).one()
    if user is None:
        raise helpers.BadRequest(errors.INVALID_USER,
                "e-mail address doesn't correspond to any user")
    # Send an e-mail with a special link.
    msg = reset_password_email(user.id)
    mail.send(email, "Password reset", msg)  # TODO check that it went through.
    return helpers.success()


def reset_password_email(uid):
    ts = int(time.time())  # Current timestamp.
    mac = mail.sign(uid, ts)  # Message authentication code.
    url = PASSWORD_RESET_URL % (uid, ts, mac)
    msg = "You recently asked to reset your GroupStreamer password. "
    msg += "To complete\nthe reset, please follow this link:\n\n" + url
    msg += "\n\nDidn't request a password reset? Please ignore this e-mail."
    return msg


if __name__ == '__main__':
    app.run()
