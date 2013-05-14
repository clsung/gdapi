# -*- coding: utf-8 -*-
import sys


class GoogleApiError(Exception):
    """An exception thrown when a Drive API return non-2xx status code"""
    default_message = 'code: %(code)s , message: %(message)s'

    def __init__(self, code=None, message=None):
        self.code = code
        self.message = message

    def __str__(self):
        keys = {}
        for k, v in self.__dict__.iteritems():
            if isinstance(v, unicode):
                v = v.encode(sys.getfilesystemencoding())
            keys[k] = v
        return str(self.default_message % keys)

    def __unicode__(self):
        return unicode(self.default_message) % self.__dict__

    def __reduce__(self):
        return (self.__class__, (), self.__dict__.copy(), )

    @property
    def message(self):
        return self.__unicode__()
