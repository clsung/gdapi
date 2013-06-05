# -*- coding: utf-8 -*-
import sys
import logging
from functools import wraps
from math import floor
from time import sleep
from random import randint


def retry(ExceptionToHandle, tries, delay=3, backoff=2, logger_name=None):
    '''Retries a function or method until it returns True.

    delay sets the initial delay in seconds. tries must be at least 0,
    and delay greater than 0.'''

    tries = floor(tries)
    if tries < 0:
        raise ValueError("tries must be 0 or greater")

    if delay <= 0:
        raise ValueError("delay must be greater than 0")

    if logger_name:
        logger = logging.getLogger(logger_name)
    else:
        logger = logging.getLogger('gdapi.utils.retry')

    def deco_retry(f):
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay  # make mutable

            while mtries >= 1:
                try:
                    return f(*args, **kwargs)  # first attempt
                except ExceptionToHandle as e:
                    import traceback
                    if 'socket.gaierror' in repr(e):  # no network
                        sleep(9.5 + randint(0, 1000) / 1000)
                        msg = "No network, retry in 10 sec"
                        logger.debug(msg)
                    else:
                        msg = "Retrying in %d seconds... %d Reason: %s, %s" % (
                            mdelay, mtries, repr(e), repr(traceback.format_tb(
                                sys.exc_info()[2])))
                        logger.debug(msg)
                        mtries -= 1      # consume an attempt
                        sleep(mdelay)  # wait...
                        mdelay = min(mdelay * backoff, 600)  # max 10 mins
            return False  # Ran out of tries :-(

        return wraps(f)(f_retry)  # true decorator -> decorated function
    return deco_retry
