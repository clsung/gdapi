# -*- coding: utf-8 -*-
import os
import unittest
from mock import patch
# mock the retry decorator before any module loads it
patch('gdapi.utils.retry', lambda x, y, delay: lambda z: z).start()
from gdapi.apirequest import APIRequest
from gdapi.errors import GoogleApiError
import requests
import tempfile
from testfixtures import compare, ShouldRaise
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


class Test_bugfix(unittest.TestCase):
    """Test function unit from given issue"""
    def setUp(self):
        pass

    @patch.object(requests.Session, 'request')
    def test_resumable_file_update_header(self, sess):
        fd, temp_path = tempfile.mkstemp()
        os.write(fd, json.dumps({
            'access_token': 'ACCESS',
            'refresh_token': 'REFRESH',
            'client_id': 'ID',
            'client_secret': 'SECRET',
        }))
        os.close(fd)  # we use temp_path only
        ar = APIRequest(temp_path)
        ar.resumable_file_update('id_a', temp_path)

        golden_header = {
            'content-type': 'application/json',
            'Authorization': 'Bearer ACCESS'
        }
        sess.assert_called_with(
            'PUT', 'https://www.googleapis.com//upload/drive/v2/files/id_a',
            files=None, stream=None, verify=True, headers=golden_header,
            params={'uploadType': 'resumable'}, data=None)

        ar.resumable_file_update('id_b', temp_path, etag="hi")

        golden_header = {
            'content-type': 'application/json',
            'Authorization': 'Bearer ACCESS',
            'If-Match': 'hi'
        }
        sess.assert_called_with(
            'PUT', 'https://www.googleapis.com//upload/drive/v2/files/id_b',
            files=None, stream=None, verify=True, headers=golden_header,
            params={'uploadType': 'resumable'}, data=None)

    @patch.object(requests.Session, 'request', autospec=True)
    @patch('requests.Response')
    def test_resumable_file_update_raise_etag(self, mock_resp, sess):
        mock_resp.status_code = 412
        mock_resp.content = "Precondition error"
        sess.return_value = mock_resp
        fd, temp_path = tempfile.mkstemp()
        os.write(fd, json.dumps({
            'access_token': 'ACCESS',
            'refresh_token': 'REFRESH',
            'client_id': 'ID',
            'client_secret': 'SECRET',
        }))
        os.close(fd)  # we use temp_path only
        ar = APIRequest(temp_path)

        with ShouldRaise(GoogleApiError(code=412,
                                        message='Precondition error')):
            ar.resumable_file_update('id_b', temp_path, etag="hi")
