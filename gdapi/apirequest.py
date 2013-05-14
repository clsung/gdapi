# -*- coding: utf-8 -*-
import os
import logging
import requests
import json
from utils import retry
from errors import GoogleApiError


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
            with open(self._credential_path, 'rb') as fin:
                self._credential.update(json.load(fin))

    def _save_credential_file(self):
        with open(self._credential_path, 'wb') as f:
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

    @retry(requests.ConnectionError, 10, delay=1)
    def _oauth_api_request(self,
                           method,
                           params=None,
                           data=None,
                           headers=None,
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
        from timeit import default_timer as timer
        url = self._TOKEN_URL
        start = timer()
        resp = requests.request(
            method,
            url,
            params=params,
            data=data,
            headers=headers,
            verify=verify,
        )
        self._logger.info(u'%s %r %s %d params %r data %r headers %r', method,
                          timer() - start, url,
                          resp.status_code, params, data, headers)
        if self._is_failed_status_code(resp.status_code):
            self._logger.debug(u'%s %s failed with response %s',
                               method, url, resp.content)
        self._error['code'] = resp.status_code
        self._error['reason'] = resp.reason
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
    def resumable_file_upload(self,
                              local_path,
                              body,
                              verify=True):
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

        :returns:
            Response from the API call.
        :rtype:
            `dict`
        """
        self._logger.debug(u"file {0} with body {1}"
                           "".format(local_path, body))
        req = requests.Session()
        resp = req.request(
            'POST',
            ''.join([self._API_URL, '/upload/drive/v2/files']),
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
                    raise requests.ConnectionError
                raise GoogleApiError(
                    code=resp.status_code,
                    message=error.get('message', resp.content))
            self._error['code'] = resp.status_code
            self._error['reason'] = resp.reason
            return None
        resumable_url = resp.headers.get('location', None)
        if resumable_url is None:
            self._error['code'] = resp.status_code
            self._error['reason'] = 'No resumable url {0}'.format(
                resp.headers)
            return None
        with open(local_path, 'rb') as f:
            resp = req.post(resumable_url, data=f)
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
                    raise requests.ConnectionError
                raise GoogleApiError(
                    code=resp.status_code,
                    message=error.get('message', resp.content))
            self._error['code'] = resp.status_code
            self._error['reason'] = resp.reason
            return None
        return resp.json()

    @retry(requests.ConnectionError, 5, delay=1)
    def resumable_file_update(self,
                              file_id,
                              local_path,
                              headers=None,
                              verify=True):
        """Create a file.

        :param file_id:
            The name of the file to update.
        :type file_id:
            `unicode`.

        :param local_path:
            local_path
        :type local_path:
            `unicode`.

        :param headers:
            Request headers.
        :type headers:
            `dict`.

        :param etag:
            (Optional) to be append to If-Match.
        :type etag:
            `unicode`

        :returns:
            Response from the API call.
        :rtype:
            `dict`
        """
        # we should update file meta first, then the content
        req = requests.Session()

        while True:  # always update latest etag/description
            self._logger.debug(u"Update file with fileId: {0}"
                               "".format(file_id))
            resp = req.put(
                ''.join(
                    [self._API_URL, '/upload/drive/v2/files/', file_id]),
                params={'uploadType': 'resumable'},
                headers=self._default_headers,
                verify=verify)

            self._logger.info(u'%d', resp.status_code)
            if self._is_failed_status_code(resp.status_code):
                if self._is_server_side_error_status_code(resp.status_code):
                    # raise to retry
                    raise requests.ConnectionError
                elif resp.status_code == 401:  # need to refresh token
                    self._logger.debug('Need to refresh token')
                    if self.refresh_access_token():  # retry on success
                        raise requests.ConnectionError
                else:
                    self._logger.debug(
                        u'Update file failed with response %s',
                        resp.content)
                    self._error['code'] = resp.status_code
                    self._error['reason'] = resp.reason
                    return None
                pass
            else:
                self._logger.debug(resp.headers)
                resumable_url = resp.headers.get('location', None)
                if resumable_url is None:
                    self._error['code'] = resp.status_code
                    self._error['reason'] = 'No resumable url {0}'.format(
                        resp.headers)
                    return None
                break
        # update content
        while True:
            with open(local_path, 'rb') as f:
                resp = req.put(resumable_url,
                               data=f, verify=False)
            if self._is_failed_status_code(resp.status_code):
                if self._is_server_side_error_status_code(resp.status_code):
                    # raise to retry
                    raise requests.ConnectionError
                elif resp.status_code == 401:  # need to refresh token
                    self._logger.debug('Need to refresh token')
                    # TODO add refresh token
                    if self.refresh_access_token():  # retry on success
                        raise requests.ConnectionError
                elif resp.status_code == 404:  # precondition error
                    self._logger.debug(
                        '404, Google Best Practise says retry:'
                        'https://developers.google.com/drive/'
                        'manage-uploads#best-practices')
                    raise requests.ConnectionError
                else:
                    self._logger.debug(
                        u'Update file failed with response %s',
                        resp.content)
                    self._error['code'] = resp.status_code
                    self._error['reason'] = resp.reason
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
        from timeit import default_timer as timer
        from urlparse import urljoin

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
        start = timer()
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
        if self._is_server_side_error_status_code(resp.status_code):
            self._logger.debug(resp)
            # raise to retry
            raise requests.ConnectionError
        if resp.status_code == 401:  # raise to retry
            self._logger.debug('Need to refresh token')
            if self._refresh_access_token():  # retry on success
                raise requests.ConnectionError
        self._logger.info(u'%s %r %s %d params %s data %s', method,
                          timer() - start, url,
                          resp.status_code, params, data)
        if self._is_failed_status_code(resp.status_code):
            self._logger.debug(u'%s %s failed with response %r',
                               method, url, resp.content)
        self._error['code'] = resp.status_code
        self._error['reason'] = resp.reason
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