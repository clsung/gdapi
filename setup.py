#!/usr/bin/env python
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

test_requirements = ['nose', 'mock', 'testfixtures', 'httpretty']
config = {
    'description': 'Google Drive API Wrapper',
    'author': 'Cheng-Lung Sung',
    'url': 'https://github.com/clsung/gdapi',
    'download_url': 'http://pypi.python.org/pypi/gdapi',
    'author_email': 'clsung@gmail.com',
    'version': '0.2.1',
    'test_requires': test_requirements,
    'install_requires': ['requests'],
    'packages': ['gdapi'],
    'scripts': ['script/download_to_somewhere.py',
                'script/upload_to_root.py'],
    'name': 'gdapi'
}

setup(**config)
