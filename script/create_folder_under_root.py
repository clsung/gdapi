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
        sys.exit("Usage: {0} <folder_name>".format(argv[0]))
    folder_name = argv[1]

    logger = logging.getLogger('gdapi')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    ga = GDAPI('./cred.json')
    ga.create_folder('root', folder_name)


if __name__ == '__main__':
    main(sys.argv)
