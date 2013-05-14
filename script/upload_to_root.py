#!/usr/bin/env python
import os
import sys
import logging

path = os.getcwd()
if path not in sys.path:
    sys.path.append(path)

from gdapi.gdapi import GDAPI


def main(argv):
    if len(argv) < 1:
        sys.exit("Usage: {0} <file>".format(argv[0]))
    file_path = argv[1]
    if not os.path.isfile(file_path):
        sys.exit("File is not exist")

    logger = logging.getLogger('gdapi')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    ga = GDAPI('./cred.json')
    ga.create_or_update_file('root', file_path, os.path.basename(file_path))


if __name__ == '__main__':
    main(sys.argv)
