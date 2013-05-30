#!usr/bin/env python
import hashlib
import hmac
import json
import libunison.utils as uutils
import re
import urllib2


# Adapted from the Django project:
# http://code.djangoproject.com/svn/django/trunk/django/core/validators.py
EMAIL_RE = re.compile(
  # dot-atom
  r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"
  # quoted-string, see also http://tools.ietf.org/html/rfc2822#section-3.2.5
  r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-\011\013\014\016-\177])*"'
  r')@((?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?$)'  # domain
  # literal form, ipv4 address (SMTP 4.1.3)
  r'|\[(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\]$',
  re.IGNORECASE
)

# Postmark related constants.
API_ENDPOINT = 'http://api.postmarkapp.com/email'


def is_valid(email):
    # Adapted from the Django project:
    # http://code.djangoproject.com/svn/django/trunk/django/core/validators.py
    parts = email.split(u'@')
    try:
        parts[-1] = parts[-1].encode('idna')
    except UnicodeError:
        return False
    email = u'@'.join(parts)
    if EMAIL_RE.search(email) is not None:
        return True
    return False


def send(recipient, subject, txt, html=None, dry_run=False):
    """Send an e-mail through the Postmark API."""
    if not is_valid(recipient):
        raise ValueError('recipient address is invalid')
    config = uutils.get_config()
    data = {
      'From': config['email']['from'],
      'To': recipient,
      'Subject': subject,
      'TextBody': txt,
    }
    if html is not None:
        data['HtmlBody'] = html
    json_data = json.dumps(data)
    # Talk to Postmark.
    req = urllib2.Request(API_ENDPOINT)
    req.add_header('Accept', 'application/json')
    req.add_header('Content-Type', 'application/json')
    if dry_run:
        req.add_header('X-Postmark-Server-Token', 'POSTMARK_API_TEST')
    else:
        req.add_header('X-Postmark-Server-Token', config['email']['key'])
    req.add_data(json_data)
    url = urllib2.urlopen(req)
    # Postmark returns some info in a JSON struct.
    return json.loads(url.read())


def sign(*values):
    """Generate a MAC for a list of values (e.g. to sign URL params)."""
    config = uutils.get_config()
    data = "".join(str(val) for val in values)
    mac = hmac.new(config['email']['salt'], data, hashlib.sha256)
    return uutils.b64enc(mac.digest()[:16])


def verify(mac, *values):
    """Verify a MAC."""
    return mac == sign(*values)
