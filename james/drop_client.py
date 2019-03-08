import dropbox
import os
from dropbox.files import WriteMode
from contextlib import closing

class DropClient:

    def __init__(self):
        try:
            TOKEN = os.environ.get('dropbox_token')
        except Exception:
            TOKEN = None

        # Check for an access token
        if TOKEN is None:
            sys.exit("ERROR: Looks like you didn't add your access token.")

        # Create an instance of a Dropbox class, which can make requests to the API.
        self.dbx = dropbox.Dropbox(TOKEN)

        # Check that the access token is valid
        try:
            self.dbx.users_get_current_account()
        except Exception:
            sys.exit("ERROR: Invalid access token; try re-generating an "
                     "access token from the app console on the web.")

    def upload_file(self, upload_path, data):
        self.dbx.files_upload(data, upload_path, mode=WriteMode('overwrite'))

    def download_file(self, download_path):
        # Find latest rev
        rev = self.dbx.files_list_revisions(download_path, limit=1).entries[0].rev
        # Restore that rev on dropbox
        self.dbx.files_restore(download_path, rev)
        # Download the file to local file
        meta, response = self.dbx.files_download(download_path, rev)
        with closing(response):
            return response.content
        raise Exception("Failed to download file")