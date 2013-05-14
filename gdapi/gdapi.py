# -*- coding: utf-8 -*-
import logging
import json
from .apirequest import APIRequest


class GDAPI(object):
    """Google Drive Wrapperd API"""

    _ITEM_TYPE_FOLDER = 'application/vnd.google-apps.folder'
    _ITEM_TYPE_FILE = 'application/octet-stream'

    def __init__(self,
                 credential_path=None):
        """
        :param credential_path:
            Authentication file to use.
        :type credential_path:
            `unicode`
        """
        self._logger = logging.getLogger(u"gdapi.%s" % self.__class__.__name__)
        self._googleapi = APIRequest(credential_path)

    def get_file_meta(self, file_id):
        self._logger.debug(file_id)
        status_code, drive_file = self._googleapi.api_request(
            'GET',
            '/drive/v2/files/{0}'.format(file_id),
        )
        return drive_file

    def create_file(self, parent_id, file_path, title,
                    description=None, mime_type=None):
        """Upload a file.

        :param parent_id:
            The id of the parent.
        :type parent_id:
            `unicode`

        :param file_path:
            file_path
        :type enc_file_path:
            `str`.

        :param title:
            The name of the file to create.
        :type title:
            `unicode`.

        :param description:
            The description of the file.
        :type md5:
            `str`

        :returns:
            Response from the API call.
        :rtype:
            `dict`
        """
        self._logger.debug(u"Upload file {0} "
                           "under folder {1}".format(title, parent_id))
        if mime_type is None:
            mime_type = self._ITEM_TYPE_FILE
        body = {
            'title': title,
            'parents': [{'id': parent_id}],  # gd allow multi-parent
            'mimeType': mime_type,
        }
        if description is not None:
            body.update({'description': description})
        self._logger.debug(json.dumps(body))

        return self._googleapi.resumable_file_upload(
            file_path, body)

    def create_or_update_file(self, parent_id, file_path, title):
        """Upload new file or update file."""
        param = {
            'q': u"trashed=false and title='{0}' and "
            "'{1}' in parents".format(title, parent_id),
            'maxResults': 1,  # only query top 1
        }
        status_code, files = self._googleapi.api_request(
            'GET',
            '/drive/v2/files',
            params=param,
        )
        if not files.get('items', []):
            # no such file
            return self.create_file(parent_id, file_path, title)
        else:
            return self.update_file(files['items'][0]['id'], file_path)

    def download_file(self, file_id, file_path):
        """Download a file.

        :param file_id:
            The id of the file to download.
        :type file_id:
            `unicode`

        :param file_path:
            file_path to save.
        :type file_path:
            `unicode`.

        :returns:
            If the operation success.
        :rtype:
            `boolean`
        """
        self._logger.debug(u"Download file {0} to {1}".format(
            file_id, file_path))
        drive_file = self.get_file_meta(file_id)
        if drive_file is None:
            return False
        status_code, resp = self._googleapi.api_request(
            'GET', drive_file['downloadUrl'], stream=True)
        if self._googleapi.error['code'] == 200:
            with open(file_path, 'wb') as f:
                while True:
                    data = resp.raw.read(8192)
                    if not data:
                        break
                    f.write(data)
        return True

    def update_file(self, file_id, file_path):
        """Upload a file.

        :param file_id:
            The id of the file to update.
        :type file_id:
            `unicode`

        :param file_path:
            file_path
        :type file_path:
            `unicode`.

        :returns:
            Response from the API call.
        :rtype:
            `dict`
        """
        self._logger.debug(u"Update file {0}".format(file_id))
        return self._googleapi.resumable_file_update(
            file_id, file_path)

    def make_user_writer_for_file(self, file_id, user_email):
        """The api for share file/folder"""
        return self._make_user_role_for_file(
            file_id, user_email, 'writer')

    def make_user_reader_for_file(self, file_id, user_email):
        """The api for share file/folder"""
        return self._make_user_role_for_file(
            file_id, user_email, 'reader')

    def _make_user_role_for_file(self, file_id, user_email, role):
        self._logger.debug(u"Make file {0} {2} by email {1}"
                           "".format(file_id, user_email, role))
        status_code, perm = self._googleapi.api_request(
            'POST',
            '/drive/v2/files/{0}/permissions'.format(file_id),
            params={'sendNotificationEmails': 'false'},
            data={
                'role': role,
                'type': 'user',
                'value': user_email
            },
        )
        self._logger.debug(perm)
        return perm


if __name__ == '__main__':
    logger = logging.getLogger('gdapi.GDAPI')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    api = GDAPI()
