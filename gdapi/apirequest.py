# -*- coding: utf-8 -*-
import os
import logging
import requests
import json
try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin  # 3.*
from .utils import retry
from .errors import GoogleApiError


class APIRequest(object):
    """Wrapperd API Request for Google API"""

    _API_URL = 'https://www.googleapis.com/'
    _TOKEN_URL = 'https://accounts.google.com/o/oauth2/token'

    def __init__(self,
                 credential_path):
        """
        :param credential_path:
            Authentication file to use.
        :type credential_path:
            `unicode`
        """
        self._logger = logging.getLogger(u"gdapi.%s" % self.__class__.__name__)
        self._credential = {'access_token': 'N/A'}
        self._credential_path = credential_path
        self._error = {'code': 0, 'reason': ''}
        self._read_credential_file()
        self._default_headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {0}'.format(
                self._credential['access_token']),
        }

    def _read_credential_file(self):
        if os.path.isfile(self._credential_path):
            with open(self._credential_path, 'r') as fin:
                self._credential.update(json.load(fin))

    def _save_credential_file(self):
        with open(self._credential_path, 'w') as f:
            json.dump(self._credential, f, indent=2)

    def _is_failed_status_code(self, status_code):
        """Returns whether the status code indicates failure."""
        return (status_code < requests.codes.OK
                or status_code >= requests.codes.MULTIPLE_CHOICES)

    def _is_server_side_error_status_code(self, status_code):
        """Returns whether the status code indicates server failure."""
        # 500~510
        return (status_code <= requests.codes.NOT_EXTENDED
                and status_code >= requests.codes.SERVER_ERROR)

    def _api_request(self,
                     method,
                     url,
                     session=None,
                     headers=None,
                     params=None,
                     data=None,
                     files=None,
                     verify=None,
                     stream=None):
        """The real request function call"""
        from timeit import default_timer as timer
        start = timer()
        if session is not None:
            resp = session.request(
                method,
                url,
                params=params,
                data=data,
                headers=headers,
                files=files,
                verify=verify,
                stream=stream,
            )
        else:
            resp = requests.request(
                method,
                url,
                params=params,
                data=data,
                headers=headers,
                files=files,
                verify=verify,
                stream=stream,
            )
        self._logger.info(u'%s %r %s %d headers %s params %s data %s', method,
                          timer() - start, url,
                          resp.status_code, headers, params, data)
        self._error['code'] = resp.status_code
        self._error['reason'] = resp.reason
        return resp

    @retry(requests.ConnectionError, 10, delay=1)
    def _oauth_api_request(self,
                           method,
                           params=None,
                           data=None,
                           verify=True):
        """Make an OAUTH 2 API call. Used to refresh the access token.

        :param method:
            Method to use for the call.
        :type method:
            `str`

        :param params:
            Parameters to be sent in the query string of the call.
        :type params:
            `dict`

        :param data:
            The data to send in the body of the request.
        :type data:
            `dict`

        :param headers:
            The headers to use for the call.
        :type headers:
            `dict`

        :param verify:
            If need to verify the cert.
        :type verify:
            `boolean`

        :returns:
            A tuple of the status code of the response and the response itself.
        :rtype:
            `tuple`
        """
        resp = self._api_request(
            method,
            self._TOKEN_URL,
            params=params,
            data=data,
            verify=verify,
        )
        return resp.status_code, resp.json()

    def _refresh_access_token(self):
        status_code, jobj = self._oauth_api_request(
            'POST',
            data={
                'client_id': self._credential['client_id'],
                'client_secret': self._credential['client_secret'],
                'grant_type': 'refresh_token',
                'refresh_token': self._credential['refresh_token']
            },
        )
        if self._is_failed_status_code(status_code):
            return False
        if jobj.get('access_token') is None:
            self._error['code'] = -1
            self._error['reason'] = ('Refresh token success, but not '
                                     'receiving access_token: '
                                     '{0}'.format(jobj))
            self._logger.error(self._error['reason'])
            return False
        self._credential.update(jobj)
        self._save_credential_file()
        self._default_headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {0}'.format(
                self._credential['access_token']),
        }
        return True

    @retry(requests.ConnectionError, 5, delay=1)
    def multipart_file_upload(self,
                              local_path,
                              body,
                              verify=True):
        with open(local_path, "rb") as f:
            file_content = f.read()
        import base64
        headers = self._default_headers
        boundary = 'xiIdabcdyl172dfasyd937845asdf'
        headers['content-type'] = ('multipart/related; '
                                   'boundary="{0}"'.format(boundary))
        parts = []
        parts.append('--' + boundary)
        parts.append('Content-Type: application/json')
        parts.append('')
        parts.append(json.dumps(body))
        parts.append('--' + boundary)
        parts.append('Content-Type: application/octet-stream')
        parts.append('Content-Transfer-Encoding: base64')
        parts.append('')
        parts.append(base64.b64encode(file_content))
        parts.append('--' + boundary + '--')
        parts.append('')
        body = '\r\n'.join(parts)

        resp = self._api_request(
            'POST',
            urljoin(self._API_URL, '/upload/drive/v2/files'),
            params={'uploadType': 'multipart'},
            headers=headers,
            data=body,
            verify=verify,)
        if self._is_failed_status_code(resp.status_code):
            if self._is_server_side_error_status_code(resp.status_code):
                # raise to retry
                raise requests.ConnectionError
            elif resp.status_code == 401:  # need to refresh token
                self._logger.debug('Need to refresh token')
                if self._refresh_access_token():  # retry on success
                    raise requests.ConnectionError
            else:  # need to log 'request exception' to file
                   # and notify user via UI
                try:
                    error = resp.json().get('error', {})
                except:
                    pass
                if error.get('code') == 403 and \
                   error.get('errors')[0].get('reason') \
                   in ['rateLimitExceeded', 'userRateLimitExceeded']:
                    self._logger.debug('Rate limit, retry')
                    self._logger.debug(error)
                    raise requests.ConnectionError
                raise GoogleApiError(
                    code=resp.status_code,
                    message=error.get('message', resp.content))
            return None
        return resp.json()

    @retry(requests.ConnectionError, 5, delay=1)
    def resumable_file_upload_v1(self,
                                 fp,
                                 body,
                                 verify=True):
        """Create a file.

        :param fp:
            file object or file path.
        :type fp:
            `file object` or `unicode`.

        :param headers:
            Request headers.
        :type headers:
            `dict`.

        :param body:
            Request body.
        :type body:
            `dict`.

        :returns:
            Response from the API call.
        :rtype:
            `dict`
        """
        import xml.etree.ElementTree as ET
        self._logger.debug(u"file {0} with body {1}"
                           "".format(fp, body))
        req = requests.Session()
        req.headers.update(self._default_headers)
        headers = {
            "GData-Version": 3,
            "Content-Length": 0,
            "X-Upload-Content-Type": "application/octet-stream",
        }
        resp = self._api_request(
            'POST',
            'https://docs.google.com/feeds/upload'
            '/create-session/default/private/full?convert=false',
            session=req,
            headers=headers,
            verify=verify,)

        if self._is_failed_status_code(resp.status_code):
            if self._is_server_side_error_status_code(resp.status_code):
                # raise to retry
                raise requests.ConnectionError
            elif resp.status_code == 401:  # need to refresh token
                self._logger.debug('Need to refresh token')
                if self._refresh_access_token():  # retry on success
                    raise requests.ConnectionError
            else:  # need to log 'request exception' to file
                   # and notify user via UI
                error = resp.json().get('error', {})
                if error.get('code') == 403 and \
                   error.get('errors')[0].get('reason') \
                   in ['rateLimitExceeded', 'userRateLimitExceeded']:
                    self._logger.debug('Rate limit, retry')
                    self._logger.debug(error)
                    raise requests.ConnectionError
                raise GoogleApiError(
                    code=resp.status_code,
                    message=error.get('message', resp.content))
            return None
        resumable_url = resp.headers.get('location', None)
        if resumable_url is None:
            self._error['reason'] = 'No resumable url {0}'.format(
                resp.headers)
            return None
        if hasattr(fp, 'read'):
            resp = self._api_request(
                'POST',
                resumable_url,
                session=req,
                data=fp,
                verify=False)
        else:
            with open(fp, 'rb') as f:
                resp = self._api_request(
                    'POST',
                    resumable_url,
                    session=req,
                    data=f,
                    verify=False)
        if self._is_failed_status_code(resp.status_code):
            if self._is_server_side_error_status_code(resp.status_code):
                # raise to retry
                raise requests.ConnectionError
            elif resp.status_code == 401:  # need to refresh token
                # if 401, we still raise to retry
                self._logger.debug('Need to refresh token')
                if self._refresh_access_token():  # retry on success
                    raise requests.ConnectionError
            elif resp.status_code == 404:  # precondition error
                self._logger.debug(
                    '404, Google Best Practise says retry:'
                    'https://developers.google.com/drive/'
                    'manage-uploads#best-practices')
                raise requests.ConnectionError
            else:  # need to log 'request exception' to file
                   # and notify user via UI
                error = resp.json().get('error', {})
                if error.get('code') == 403 and \
                   error.get('errors')[0].get('reason') \
                   in ['rateLimitExceeded', 'userRateLimitExceeded']:
                    self._logger.debug('Rate limit, retry')
                    self._logger.debug(error)
                    raise requests.ConnectionError
                raise GoogleApiError(
                    code=resp.status_code,
                    message=error.get('message', resp.content))
            return None
        self._logger.debug(resp.content)
        root = ET.fromstring(resp.content)
        file_node = root.find('{http://www.w3.org/2005/Atom}id')
        # <id>https://docs.google.com/feeds/id/file%3A0B2XjOSViGRlPRGRvenZaRjh5N0E</id>
        self._logger.debug(file_node)
        file_id = file_node.text.replace(
            'https://docs.google.com/feeds/id/file%3A', '')
        self._logger.debug(file_id)

        retries = 2
        while body and retries > 0:
            retries = retries - 1
            self._logger.debug(u"Update file {0} with {1}".format(
                file_id, json.dumps(body)))
            req.headers.update(self._default_headers)
            resp = req.put(
                urljoin(self._API_URL, '/drive/v2/files/{0}'.format(
                    file_id)),
                headers=headers,
                data=json.dumps(body),
                verify=False,)
            if self._is_failed_status_code(resp.status_code):
                if self._is_server_side_error_status_code(resp.status_code):
                    # continue to retry
                    continue
                elif resp.status_code == 401:  # need to refresh token
                    self._logger.debug('Need to refresh token')
                    if self._refresh_access_token():  # retry on success
                        continue
                else:  # need to log 'request exception' to file
                    # and notify user via UI
                    error = resp.json().get('error', {})
                    if error.get('code') == 403 and \
                    error.get('errors')[0].get('reason') \
                    in ['rateLimitExceeded', 'userRateLimitExceeded']:
                        self._logger.debug('Rate limit, retry')
                        continue
                    raise GoogleApiError(code=resp.status_code,
                                        message=error.get('message', resp.content))
                self._error['code'] = resp.status_code
                self._error['reason'] = resp.reason
                return None
            drive_file = resp.json()
        self._logger.debug(drive_file)
        return drive_file

    @retry(requests.ConnectionError, 5, delay=1)
    def resumable_file_upload(self,
                              fp,
                              body,
                              verify=True):
        """Create a file.

        :param fp:
            file object or file path.
        :type fp:
            `file object` or `unicode`.

        :param headers:
            Request headers.
        :type headers:
            `dict`.

        :param body:
            Request body.
        :type body:
            `dict`.

        :returns:
            Response from the API call.
        :rtype:
            `dict`
        """
        self._logger.debug(u"file {0} with body {1}"
                           "".format(fp, body))
        req = requests.Session()
        resp = self._api_request(
            'POST',
            urljoin(self._API_URL, '/upload/drive/v2/files'),
            session=req,
            params={'uploadType': 'resumable'},
            headers=self._default_headers,
            data=json.dumps(body),
            verify=verify,)

        if self._is_failed_status_code(resp.status_code):
            if self._is_server_side_error_status_code(resp.status_code):
                # raise to retry
                raise requests.ConnectionError
            elif resp.status_code == 401:  # need to refresh token
                self._logger.debug('Need to refresh token')
                if self._refresh_access_token():  # retry on success
                    raise requests.ConnectionError
            else:  # need to log 'request exception' to file
                   # and notify user via UI
                error = resp.json().get('error', {})
                if error.get('code') == 403 and \
                   error.get('errors')[0].get('reason') \
                   in ['rateLimitExceeded', 'userRateLimitExceeded']:
                    self._logger.debug('Rate limit, retry')
                    self._logger.debug(error)
                    raise requests.ConnectionError
                raise GoogleApiError(
                    code=resp.status_code,
                    message=error.get('message', resp.content))
            return None
        resumable_url = resp.headers.get('location', None)
        if resumable_url is None:
            self._error['reason'] = 'No resumable url {0}'.format(
                resp.headers)
            return None
        if hasattr(fp, 'read'):
            resp = self._api_request(
                'POST',
                resumable_url,
                session=req,
                data=fp,
                verify=False)
        else:
            with open(fp, 'rb') as f:
                resp = self._api_request(
                    'POST',
                    resumable_url,
                    session=req,
                    data=f,
                    verify=False)
        if self._is_failed_status_code(resp.status_code):
            if self._is_server_side_error_status_code(resp.status_code):
                # raise to retry
                raise requests.ConnectionError
            elif resp.status_code == 401:  # need to refresh token
                # if 401, we still raise to retry
                self._logger.debug('Need to refresh token')
                if self._refresh_access_token():  # retry on success
                    raise requests.ConnectionError
            elif resp.status_code == 404:  # precondition error
                self._logger.debug(
                    '404, Google Best Practise says retry:'
                    'https://developers.google.com/drive/'
                    'manage-uploads#best-practices')
                raise requests.ConnectionError
            else:  # need to log 'request exception' to file
                   # and notify user via UI
                error = resp.json().get('error', {})
                if error.get('code') == 403 and \
                   error.get('errors')[0].get('reason') \
                   in ['rateLimitExceeded', 'userRateLimitExceeded']:
                    self._logger.debug('Rate limit, retry')
                    self._logger.debug(error)
                    raise requests.ConnectionError
                raise GoogleApiError(
                    code=resp.status_code,
                    message=error.get('message', resp.content))
            return None
        return resp.json()

    @retry(requests.ConnectionError, 5, delay=1)
    def simple_media_upload(self,
                            local_path,
                            headers={'content-type': 'application/json'},
                            body=None,
                            file_id=None):
        """Create a file.

        :param local_path:
            local_path
        :type local_path:
            `unicode`.

        :param headers:
            Request headers.
        :type headers:
            `dict`.

        :param body:
            Request body.
        :type body:
            `dict`.

        :param file_id:
            If no file_id, "POST", "PUT" otherwise.
        :type file_id:
            `unicode`.

        :returns:
            Response from the API call.
        :rtype:
            `dict`
        """
        self._logger.debug(u"file {0} with headers {1} body {2}"
                           "".format(local_path, headers, body))
        req = requests.Session()
        req.headers.update(self._default_headers)
        if file_id is None:
            method = 'POST'
            url = urljoin(self._API_URL, '/upload/drive/v2/files')
        else:
            method = 'PUT'
            url = urljoin(self._API_URL,
                          '/upload/drive/v2/files/{0}'.format(file_id))
        with open(local_path, 'rb') as f:
            resp = req.request(
                method,
                url,
                params={'uploadType': 'media'},
                headers=headers,
                data=f,
                verify=False,)
            self._logger.debug("{0} {1} {2}".format(
                resp.status_code, resp.headers, resp.content))
            self._logger.debug("Request header: {0}".format(
                resp.request.headers))

        self._logger.debug(resp.status_code)
        if self._is_failed_status_code(resp.status_code):
            if self._is_server_side_error_status_code(resp.status_code):
                # raise to retry
                raise requests.ConnectionError
            elif resp.status_code == 401:  # need to refresh token
                self._logger.debug('Need to refresh token')
                if self._refresh_access_token():  # retry on success
                    raise requests.ConnectionError
            else:  # need to log 'request exception' to file
                   # and notify user via UI
                error = resp.json().get('error', {})
                if error.get('code') == 403 and \
                   error.get('errors')[0].get('reason') \
                   in ['rateLimitExceeded', 'userRateLimitExceeded']:
                    self._logger.debug('Rate limit, retry')
                    raise requests.ConnectionError
                raise GoogleApiError(code=resp.status_code,
                                     message=error.get('message', resp.content))
            self._error['code'] = resp.status_code
            self._error['reason'] = resp.reason
            return None
        drive_file = resp.json()
        self._logger.debug(drive_file)
        retries = 2
        while body and retries > 0:
            retries = retries - 1
            self._logger.debug(u"Update file {0} with {1}".format(
                drive_file['id'], json.dumps(body)))
            req.headers.update(self._default_headers)
            resp = req.put(
                urljoin(self._API_URL, '/drive/v2/files/{0}'.format(
                    drive_file['id'])),
                headers=headers,
                data=json.dumps(body),
                verify=False,)
            if self._is_failed_status_code(resp.status_code):
                if self._is_server_side_error_status_code(resp.status_code):
                    # continue to retry
                    continue
                elif resp.status_code == 401:  # need to refresh token
                    self._logger.debug('Need to refresh token')
                    if self._refresh_access_token():  # retry on success
                        continue
                else:  # need to log 'request exception' to file
                    # and notify user via UI
                    error = resp.json().get('error', {})
                    if error.get('code') == 403 and \
                    error.get('errors')[0].get('reason') \
                    in ['rateLimitExceeded', 'userRateLimitExceeded']:
                        self._logger.debug('Rate limit, retry')
                        continue
                    raise GoogleApiError(code=resp.status_code,
                                        message=error.get('message', resp.content))
                self._error['code'] = resp.status_code
                self._error['reason'] = resp.reason
                return None
            drive_file = resp.json()
        self._logger.debug(drive_file)
        return drive_file

    @retry(requests.ConnectionError, 5, delay=1)
    def resumable_file_update(self,
                              file_id,
                              fp,
                              headers={},
                              body=None,
                              etag=None,
                              verify=True):
        """Create a file.

        :param file_id:
            The name of the file to update.
        :type file_id:
            `unicode`.

        :param fp:
            file object or file path.
        :type fp:
            `file object` or `unicode`.

        :param headers:
            Request headers.
        :type headers:
            `dict`.

        :param body:
            Request body.
        :type body:
            `dict`.

        :param etag:
            (Optional) to be append to If-Match.
        :type etag:
            `unicode`

        :returns:
            Response from the API call.
        :rtype:
            `dict`
        :raises: GoogleApiError.
        """
        # we should update file meta first, then the content
        req = requests.Session()

        while True:  # always update latest etag/description
            self._logger.debug(u"Update file with fileId: {0}"
                               "".format(file_id))
            if headers:
                headers.update(self._default_headers)
            else:
                headers = self._default_headers
            if etag:
                headers.update({'If-Match': etag})
            if body is not None:
                data = json.dumps(body)
            else:
                data = None
            resp = self._api_request(
                'PUT',
                urljoin(self._API_URL, '/upload/drive/v2/files/{0}'.format(
                    file_id)),
                session=req,
                params={'uploadType': 'resumable'},
                headers=headers,
                data=data,
                verify=verify)

            self._logger.info(u'%d', resp.status_code)
            if self._is_failed_status_code(resp.status_code):
                if self._is_server_side_error_status_code(resp.status_code):
                    # raise to retry
                    raise requests.ConnectionError
                elif resp.status_code == 401:  # need to refresh token
                    self._logger.debug('Need to refresh token')
                    if self._refresh_access_token():  # retry on success
                        raise requests.ConnectionError
                    else:
                        return None
                elif resp.status_code == 412:  # precondition error
                    raise GoogleApiError(
                        code=resp.status_code, message=resp.content
                    )
                else:
                    self._logger.debug(
                        u'Update file failed with response %s',
                        resp.content)
                    return None
                pass
            else:
                self._logger.debug(resp.headers)
                resumable_url = resp.headers.get('location', None)
                if resumable_url is None:
                    self._error['reason'] = 'No resumable url {0}'.format(
                        resp.headers)
                    return None
                break
        # update content
        while True:
            if hasattr(fp, 'read'):
                resp = self._api_request(
                    'PUT',
                    resumable_url,
                    session=req,
                    data=fp,
                    verify=False)
            else:
                with open(fp, 'rb') as f:
                    resp = self._api_request(
                        'PUT',
                        resumable_url,
                        session=req,
                        data=f,
                        verify=False)
            if self._is_failed_status_code(resp.status_code):
                if self._is_server_side_error_status_code(resp.status_code):
                    # raise to retry
                    raise requests.ConnectionError
                elif resp.status_code == 401:  # need to refresh token
                    self._logger.debug('Need to refresh token')
                    if self._refresh_access_token():  # retry on success
                        raise requests.ConnectionError
                    else:
                        return None
                elif resp.status_code == 404:  # precondition error
                    self._logger.debug(
                        '404, Google Best Practise says retry:'
                        'https://developers.google.com/drive/'
                        'manage-uploads#best-practices')
                    raise requests.ConnectionError
                elif resp.status_code == 412:  # precondition error
                    raise GoogleApiError(
                        code=resp.status_code, message=resp.content
                    )
                else:
                    self._logger.debug(
                        u'Update file failed with response %s',
                        resp.content)
                    return None
            else:
                break
        return resp.json()

    @retry(requests.ConnectionError, 20, delay=1)
    def api_request(self,
                    method,
                    resource,
                    params=None,
                    data=None,
                    headers=None,
                    files=None,
                    verify=False,
                    stream=False):
        """Make an API call.

        :param method:
            Method to use for the call.
        :type method:
            `str`

        :param resource:
            The resource being accessed.
        :type resource:
            `str`

        :param params:
            Parameters to be sent in the query string of the call.
        :type params:
            `dict`

        :param data:
            The data to send in the body of the request.
        :type data:
            `dict`

        :param headers:
            The headers to use for the call.
        :type headers:
            `dict`

        :param files:
            The upload files to use for the call.
        :type files:
            `dict`

        :param verify:
            If need to verify the cert.
        :type verify:
            `boolean`

        :returns:
            A tuple of the status code of the response and the response itself.
        :rtype:
            `tuple`
        """

        if resource.startswith('http'):
            url = resource
        else:
            url = urljoin(self._API_URL, resource)
        if data and not files:
            data = json.dumps(data)
        if headers:
            headers.update(self._default_headers)
        else:
            headers = self._default_headers
        resp = self._api_request(
            method,
            url,
            params=params,
            data=data,
            headers=headers,
            files=files,
            verify=verify,
            stream=stream,
        )
        if self._is_server_side_error_status_code(resp.status_code):
            self._logger.debug(resp)
            # raise to retry
            raise requests.ConnectionError
        if resp.status_code == 401:  # raise to retry
            self._logger.debug(u'Need to refresh token')
            if self._refresh_access_token():  # retry on success
                raise requests.ConnectionError
        if self._is_failed_status_code(resp.status_code):
            self._logger.debug(u'%s %s failed with response %r',
                               method, url, resp.content)
        if stream:
            return resp.status_code, resp
        try:
            return resp.status_code, resp.json()
        except ValueError:
            return resp.status_code, resp.content

    @property
    def error(self):
        return self._error


if __name__ == '__main__':
    logger = logging.getLogger('gdapi.APIRequest')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    api = APIRequest('./cred.json')
