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
from mock import mock_open


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
        with os.fdopen(fd, 'w') as f:
            json.dump({
                'access_token': 'ACCESS',
                'refresh_token': 'REFRESH',
            }, f)
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
        with open(temp_path, 'r') as f:
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
        compare(b'Hello World', resp.content)
        resp = self.ar._api_request('GET', url)
        compare(500, resp.status_code)
        compare(b'Internal Server buzz', resp.content)
        session = requests.Session()
        resp = self.ar._api_request('GET', url, session=session)
        compare(404, resp.status_code)
        compare(b'Not Found', resp.content)


class Test_bugfix(unittest.TestCase):
    """Test function unit from given issue"""
    def setUp(self):
        fd, temp_path = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as f:
            json.dump({
                'access_token': 'ACCESS',
                'refresh_token': 'REFRESH',
                'client_id': 'ID',
                'client_secret': 'SECRET',
            }, f)
        self.ar = APIRequest(temp_path)
        pass

    @patch.object(requests.Session, 'request')
    def test_resumable_file_update_header(self, sess):
        sess.return_value.status_code = 404  # fail early
        fd, temp_path = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as f:
            f.write("File content is here")
        self.ar.resumable_file_update('id_a', temp_path)

        golden_header = {
            'content-type': 'application/json',
            'Authorization': 'Bearer ACCESS'
        }
        sess.assert_called_with(
            'PUT', 'https://www.googleapis.com/upload/drive/v2/files/id_a',
            files=None, stream=None, verify=True, headers=golden_header,
            params={'uploadType': 'resumable'}, data=None)

        self.ar.resumable_file_update('id_b', temp_path, etag="hi")

        golden_header = {
            'content-type': 'application/json',
            'Authorization': 'Bearer ACCESS',
            'If-Match': 'hi'
        }
        sess.assert_called_with(
            'PUT', 'https://www.googleapis.com/upload/drive/v2/files/id_b',
            files=None, stream=None, verify=True, headers=golden_header,
            params={'uploadType': 'resumable'}, data=None)

    @patch.object(requests.Session, 'request', autospec=True)
    @patch('requests.Response')
    def test_resumable_file_update_raise_etag(self, mock_resp, sess):
        mock_resp.status_code = 412
        mock_resp.content = "Precondition error"
        sess.return_value = mock_resp

        fd, temp_path = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as f:
            f.write("File content is here")
        with ShouldRaise(GoogleApiError(code=412,
                                        message='Precondition error')):
            self.ar.resumable_file_update('id_b', temp_path, etag="hi")

    @patch.object(requests.Session, 'request')
    @patch('requests.Response')
    def test_resumable_file_upload(self, mock_resp, mock_sess):
        mock_resp.status_code = 200
        mock_resp.headers = {'location': 'https://hello.content/stream'}
        mock_sess.return_value = mock_resp

        body = {
            'title': "FileName",
            'parents': [{'id': 'root'}],
            'mimeType': 'application/octet-stream',
        }
        with patch('gdapi.apirequest.open',
                   mock_open(read_data='bibble'), create=True) as m:
            fd, temp_path = tempfile.mkstemp()
            os.close(fd)  # we use temp_path only
            self.ar.resumable_file_upload(temp_path, body)
            m.assert_called_once_with(temp_path, 'rb')
            mock_sess.assert_called_with(
                'POST', 'https://hello.content/stream', params=None,
                files=None, headers=None, stream=None, verify=False, data=m())

    @patch.object(requests.Session, 'request')
    @patch('requests.Response')
    def test_simple_media_upload(self, mock_resp, mock_sess):
        from mock import call
        from mock import ANY
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'id': 'abc'}
        mock_sess.return_value = mock_resp

        body = {
            'title': "FileName",
            'parents': [{'id': 'root'}],
            'mimeType': 'application/octet-stream',
        }
        with patch('gdapi.apirequest.open',
                   mock_open(read_data='bibble'), create=True) as m:
            fd, temp_path = tempfile.mkstemp()
            os.close(fd)  # we use temp_path only
            self.ar.simple_media_upload(temp_path, body=body)
            m.assert_called_once_with(temp_path, 'rb')
            expected = [call('POST', 'https://www.googleapis.com/upload/drive/v2/files',
                             params={'uploadType': 'media'},
                             headers=ANY, verify=False, data=m()),
                        call('PUT', 'https://www.googleapis.com/drive/v2/files/abc',
                            headers=ANY,
                             verify=False, data=json.dumps(body)),]
            mock_sess.assert_has_calls(expected)

    @patch.object(requests.Session, 'request')
    @patch('requests.Response')
    def test_resumable_file_upload_with_file_object(self,
                                                    mock_resp, mock_sess):
        mock_resp.status_code = 200
        mock_resp.headers = {'location': 'https://hello.content/object'}
        mock_sess.return_value = mock_resp

        body = {
            'title': "FileName",
            'parents': [{'id': 'root'}],
            'mimeType': 'application/octet-stream',
        }
        fd, temp_path = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as f:
            f.write("File content is here")
        with open(temp_path, 'rb') as f:
            self.ar.resumable_file_upload(f, body)
        mock_sess.assert_called_with(
            'POST', 'https://hello.content/object', params=None,
            files=None, headers=None, stream=None, verify=False, data=f)

    @patch.object(requests.Session, 'request')
    @patch('requests.Response')
    def test_resumable_file_update(self, mock_resp, mock_sess):
        mock_resp.status_code = 200
        mock_resp.headers = {'location': 'https://hello.content/stream2'}
        mock_sess.return_value = mock_resp

        with patch('gdapi.apirequest.open',
                   mock_open(read_data='bibble'), create=True) as m:
            fd, temp_path = tempfile.mkstemp()
            os.close(fd)  # we use temp_path only
            self.ar.resumable_file_update('id_b', temp_path)
            m.assert_called_once_with(temp_path, 'rb')
            mock_sess.assert_called_with(
                'PUT', 'https://hello.content/stream2', params=None,
                files=None, headers=None, stream=None, verify=False, data=m())

    @patch.object(requests.Session, 'request')
    @patch('requests.Response')
    def test_resumable_file_update_with_file_object(self,
                                                    mock_resp, mock_sess):
        mock_resp.status_code = 200
        mock_resp.headers = {'location': 'https://hello.content/object2'}
        mock_sess.return_value = mock_resp

        fd, temp_path = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as f:
            f.write("File content is here")
        with open(temp_path, 'rb') as f:
            self.ar.resumable_file_update('id_c', f)
        mock_sess.assert_called_with(
            'PUT', 'https://hello.content/object2', params=None,
            files=None, headers=None, stream=None, verify=False, data=f)
