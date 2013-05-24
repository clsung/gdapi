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
        :type description:
            `str`

        :param mime_type:
            The mime_type of the file.
        :type mime_type:
            `unicode`

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

#        return self._googleapi.multipart_file_upload(
        return self._googleapi.resumable_file_upload(
            file_path, body)

    def create_folder(self, parent_id, title):
        """Create a folder. If the same title already exists, just
        return the id of that folder.

        :param parent_id:
            The id of the parent.
        :type parent_id:
            `unicode`

        :param title:
            The name of the folder to create.
        :type title:
            `unicode`.

        :returns:
            Folder id None if failed.
        :rtype:
            `unicode`
        """
        self._logger.debug(u"Create folder {0} "
                           "under folder {1}".format(title, parent_id))
        param = {
            'q': u"trashed=false and title='{0}' and "
            "'{1}' in parents and mimeType='{2}'".format(
                title, parent_id, self._ITEM_TYPE_FOLDER),
            'maxResults': 1,  # only query top 1
        }
        status_code, folders = self._googleapi.api_request(
            'GET',
            '/drive/v2/files',
            params=param,
        )
        if not folders.get('items', []):
            # no such folder
            pass
        else:
            return folders['items'][0]['id']
        body = {
            'title': title,
            'parents': [{'id': parent_id}],  # gd allow multi-parent
            'mimeType': self._ITEM_TYPE_FOLDER,
        }
        self._logger.debug(json.dumps(body))

        status_code, drive_file = self._googleapi.api_request(
            'POST',
            '/drive/v2/files',
            data=body,
        )
        return drive_file.get('id', None)

    def create_meta_file(self, parent_id, title, description=None):
        """Create a meta-only file.

        :param parent_id:
            The id of the parent.
        :type parent_id:
            `unicode`

        :param title:
            The name of the file to create.
        :type title:
            `unicode`.

        :param description:
            The description of the file.
        :type description:
            `unicode`

        :returns:
            Response from the API call.
        :rtype:
            `dict`
        """
        self._logger.debug(u"Create meta file {0} "
                           "under folder {1}".format(title, parent_id))
        body = {
            'title': title,
            'parents': [{'id': parent_id}],  # gd allow multi-parent
        }
        if description is not None:
            body.update({'description': description})
        self._logger.debug(json.dumps(body))

        status_code, drive_file = self._googleapi.api_request(
            'POST',
            '/drive/v2/files',
            data=body,
        )
        return drive_file

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

    def unshare(self, resource_id, perm_id=None):
        """grab all perm and unshare all, except owner, anyone.
        If perm_id specified, remove that perm."""
        perms = self.query_permission(resource_id)
        if not perms:
            return False
        if perm_id:
            self._logger.debug(u"Try to remove perm {0} from file {1}"
                               u"".format(perm_id, resource_id))
            if perm_id in perms:
                status_code, _ = self._googleapi.api_request(
                    'DELETE', '/drive/v2/files/{0}/permissions/{1}'.format(
                        resource_id, perm_id))
                return True
            return False
        for perm in perms:
            if perm['role'] == u'owner' or perm['role'] == u'anyone':
                continue
            status_code, _ = self._googleapi.api_request(
                'DELETE', '/drive/v2/files/{0}/permissions/{1}'.format(
                    resource_id, perm['id']))
        return True

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

    def query_permission(self, resource_id):
        """Returns the permission list item for the Resource.

        :param resource_id:
            The id of the Resource to query permission.
        :type resource_id:
            `unicode`

        :returns:
            List of permission resource (folder).
        :rtype:
            `list`
        """
        self._logger.debug('Query permission {0}'.format(resource_id))
        status_code, perms = self._googleapi.api_request(
            'GET',
            '/drive/v2/files/{0}/permissions'.format(resource_id),
        )
        self._logger.debug(perms)
        try:
            return perms.get('items', [])
        except AttributeError:
            return []


if __name__ == '__main__':
    logger = logging.getLogger('gdapi.GDAPI')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    api = GDAPI()
