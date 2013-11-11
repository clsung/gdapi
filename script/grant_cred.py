#!/usr/bin/env python
import os
import sys
import logging
import json
import requests
import string
import random
import urlparse
import urllib
from argparse import ArgumentParser

path = os.getcwd()
if path not in sys.path:
    sys.path.append(path)

from gdapi.apirequest import APIRequest


def main(argv):
    logger = logging.getLogger('gdapi')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)

    parser = ArgumentParser()
    parser.add_argument("--code", action='store', help="code")
    parser.add_argument("--cred", action='store', help="credential path")
    parser.add_argument("--id", action='store', help="Client Id")
    parser.add_argument("--secret", action='store', help="Client Secret")
    parser.add_argument("--redirect_uri", action='store',
                        default='urn:ietf:wg:oauth:2.0:oob',
                        help="Redirect URI")
    parser.add_argument("--scope", action='store',
                        default=(
                            'https://www.googleapis.com/auth/drive.file '
                            'https://www.googleapis.com/auth/userinfo.email '
                            'https://www.googleapis.com/auth/userinfo.profile'
                        ),
                        help="Scope")
    args = parser.parse_args(argv[1:])
    if not args.id or not args.secret:
        logger.error("Client Id and Client Secret are required")
        sys.exit(-1)
    AUTH_URL = 'https://accounts.google.com/o/oauth2/auth'

    if not args.code:
        print('Please open the follow URL and paste the code here :')
        url = AUTH_URL
        params={
            'client_id': args.id,
            'scope': args.scope,
            'redirect_uri': args.redirect_uri,
            'response_type': 'code',
            'state': ''.join(random.choice
                                (string.ascii_lowercase + string.digits)
                                for x in xrange(5)),
        }
        url_parts = list(urlparse.urlparse(url))
        query = dict(urlparse.parse_qsl(url_parts[4]))
        query.update(params)

        url_parts[4] = urllib.urlencode(query)
        print(urlparse.urlunparse(url_parts))
        args.code = raw_input("Paste code here: ")

    api = APIRequest('./nowhere.json')

    resp = api._api_request(
        'POST',
        api._TOKEN_URL,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={
            'client_id': args.id,
            'client_secret': args.secret,
            'code': args.code,
            'redirect_uri': args.redirect_uri,
            'grant_type': 'authorization_code',
        }
    )
    if resp.status_code == 200:
        api._credential.update(resp.json())
        api._save_credential_file()
        logger.info("Success created the credential file")
    else:
        logger.error(resp.reason)


if __name__ == '__main__':
    main(sys.argv)
