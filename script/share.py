#!/usr/bin/env python
import os
import sys
import logging

path = os.getcwd()
if path not in sys.path:
    sys.path.append(path)

from gdapi.gdapi import GDAPI


def main(argv):
    if len(argv) < 2:
        sys.exit("Usage: {0} <file_id> <email>".format(argv[0], argv[1]))
    file_id = argv[1]
    email = argv[2]

    logger = logging.getLogger('gdapi')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    ga = GDAPI('./cred.json')
    ga.make_user_reader_for_file(file_id, email)


if __name__ == '__main__':
    main(sys.argv)
