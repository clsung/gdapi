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
        sys.exit("Usage: {0} <file_id> <dest_path>".format(argv[0]))
    file_id = argv[1]
    dest_path = argv[2]
    if os.path.isdir(dest_path):
        sys.exit("Destination is folder")

    logger = logging.getLogger('gdapi')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    ga = GDAPI('./cred.json')
    ga.download_file(file_id, dest_path)


if __name__ == '__main__':
    main(sys.argv)
