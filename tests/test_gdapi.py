# -*- coding: utf-8 -*-
import unittest
from mock import patch
# mock the retry decorator before any module loads it
patch('gdapi.utils.retry', lambda x, y, delay: lambda z: z).start()
from gdapi.gdapi import GDAPI


class Test_upload_file(unittest.TestCase):
    """Test function unit from given issue"""
    def setUp(self):
        self.gd = GDAPI()
        pass

    def tearDown(self):
        pass
