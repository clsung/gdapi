#!/usr/bin/env python
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'Google Drive API Wrapper',
    'author': 'Cheng-Lung Sung',
    'url': 'https://github.com/clsung/gdapi',
    'download_url': 'http://pypi.python.org/pypi/gdapi',
    'author_email': 'clsung@gmail.com',
    'version': '0.0.1',
    'install_requires': ['nose', 'mock'],
    'packages': ['gdapi'],
    'scripts': ['download_to_somewhere.py', 'upload_to_root.py'],
    'name': 'gdapi'
}

setup(**config)
