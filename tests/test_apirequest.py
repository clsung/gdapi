# -*- coding: utf-8 -*-
import os
import unittest
from mock import patch
# mock the retry decorator before any module loads it
patch('gdapi.utils.retry', lambda x, y, delay: lambda z: z).start()
from gdapi.apirequest import APIRequest
import requests
import tempfile
from testfixtures import compare
import httpretty
import json


class Test_cred_functions(unittest.TestCase):
    """Test function unit from given issue"""
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_init_no_cred(self):
        fd, temp_path = tempfile.mkstemp()
        os.close(fd)  # we use temp_path only
        os.unlink(temp_path)  # ensure this is not exist
        ar = APIRequest(temp_path)
        compare({'access_token': 'N/A'}, ar._credential)

    def test_read_cred(self):
        fd, temp_path = tempfile.mkstemp()
        os.write(fd, json.dumps({
            'access_token': 'ACCESS',
            'refresh_token': 'REFRESH',
        }))
        os.close(fd)  # we use temp_path only
        ar = APIRequest(temp_path)
        compare('ACCESS', ar._credential['access_token'])
        compare('REFRESH', ar._credential['refresh_token'])
        pass

    def test_write_cred(self):
        fd, temp_path = tempfile.mkstemp()
        os.close(fd)
        os.unlink(temp_path)  # ensure this is not exist
        ar = APIRequest(temp_path)
        ar._credential['access_token'] = '12345'
        ar._credential['client_id'] = '54321'
        ar._save_credential_file()
        with open(temp_path, 'rb') as f:
            jobj = json.load(f)
        compare(jobj, ar._credential)
        pass


class Test_api_functions(unittest.TestCase):
    """Test function unit from given issue"""
    def setUp(self):
        fd, temp_path = tempfile.mkstemp()
        os.close(fd)  # we use temp_path only
        os.unlink(temp_path)
        self.ar = APIRequest(temp_path)
        pass

    def tearDown(self):
        pass

    def test_failed_status_code(self):
        compare(True, self.ar._is_failed_status_code(500))
        for x in [200, 201, 202, 203, 204]:
            compare(False, self.ar._is_failed_status_code(x))
        for x in [400, 404, 401, 500, 503, 502]:
            compare(True, self.ar._is_failed_status_code(x))

    def test_server_side_error_status_code(self):
        for x in [500, 503, 502]:
            compare(True, self.ar._is_server_side_error_status_code(x))
        for x in [400, 404, 403]:
            compare(False, self.ar._is_server_side_error_status_code(x))
        for x in [200, 201, 204]:
            compare(False, self.ar._is_server_side_error_status_code(x))

    @httpretty.activate
    def test_api_request(self):
        url = 'https://gdapi.com/info'
        httpretty.register_uri(
            httpretty.GET,
            url,
            responses=[
                httpretty.Response(body="Hello World", status=200),
                httpretty.Response(body="Internal Server buzz", status=500),
                httpretty.Response(body="Not Found", status=404),
            ])
        resp = self.ar._api_request('GET', url)
        compare(200, resp.status_code)
        compare('Hello World', resp.content)
        resp = self.ar._api_request('GET', url)
        compare(500, resp.status_code)
        compare('Internal Server buzz', resp.content)
        session = requests.Session()
        resp = self.ar._api_request('GET', url, session=session)
        compare(404, resp.status_code)
        compare('Not Found', resp.content)
