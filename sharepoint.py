import requests
import json
import os
import logging
from dotenv import load_dotenv
import urllib

load_dotenv()
logger=logging.getLogger(__name__)

class Sharepoint:
    def __init__(self,client_id=None,client_secret=None,tenant_id=None,tenant_url=None,site_name=None):
        self.CLIENT_ID = client_id if client_id else os.getenv('CLIENT_ID')
        self.CLIENT_SECRET = client_secret if client_secret else os.getenv('CLIENT_SECRET')
        self.TENANT_ID = tenant_id if tenant_id else os.getenv('TENANT_ID')
        self.TENANT_URL = tenant_url if tenant_url else os.getenv('TENANT_URL')
        self.SITE_NAME = site_name if site_name else os.getenv('SITE_NAME')
        self.RESOURCE = "00000003-0000-0ff1-ce00-000000000000" + "/" + self.TENANT_URL + "@" + self.TENANT_ID
        self.TOKEN_URI = "https://accounts.accesscontrol.windows.net/" + self.TENANT_ID + "/tokens/OAuth/2"
        self.TOKEN=self.generate_sp_token()
        self.RECORDINGS_FOLDER= os.getenv('RECORDINGS_FOLDER') if os.getenv('RECORDINGS_FOLDER') else 'Recordings'

    def generate_sp_token(self):

        # Construct Body
        body = {
            "client_id": self.CLIENT_ID,
            "resource": self.RESOURCE,
            "client_secret": self.CLIENT_SECRET,
            "grant_type": "client_credentials",
        }

        header = {
            "ContentType": "application/x-www-form-urlencoded"
        }
        logger.info('Exchanging for Auth Token from Microsoft ...')
        response = requests.request(method='POST', url=self.TOKEN_URI, data=body, headers=header)
        response_data = json.loads(response.text)
        logger.debug(response.status_code, response_data)

        return response_data['access_token']

    def get_projects_folder(self):
        apiUrl = f"https://{self.TENANT_URL}/sites/{self.SITE_NAME}/_api/web/GetFolderByServerRelativeUrl('Shared Documents/{self.RECORDINGS_FOLDER}')"

        header = {
            "Authorization": "Bearer " + self.TOKEN,
            "Accept": "application/json;odata=verbose",
            "ContentType": "application/json"
        }

        response = requests.request(method='GET', url=apiUrl, headers=header)
        response_data = json.loads(response.text)
        logger.debug(response.status_code, response_data)

        return response

    def create_folder(self, folder_name):
        apiUrl = f"https://{self.TENANT_URL}/sites/{self.SITE_NAME}/_api/web/folders"

        header = {
            "Authorization": "Bearer " + self.TOKEN,
            "Accept": "application/json;odata=verbose",
            "Content-Type": "application/json;odata=verbose",
            "X-RequestDigest": self.get_message_digest()
        }

        body = {'__metadata': {'type': 'SP.Folder'},
                'ServerRelativeUrl': f"/sites/{self.SITE_NAME}/Shared Documents/" + folder_name}

        logger.info(f'Creating Folder {body["ServerRelativeUrl"]}')
        response = requests.request(method='POST', url=apiUrl, data=json.dumps(body), headers=header)
        response_data = json.loads(response.text)
        logger.debug(response.status_code,response_data)
        return response_data

    def get_message_digest(self):
        apiUrl = f"https://{self.TENANT_URL}/sites/{self.SITE_NAME}/_api/contextinfo"

        header = {
            "Authorization": "Bearer " + self.TOKEN,
            "Accept": "application/json;odata=verbose",
            "ContentType": "application/json"
        }
        logger.info('Obtaining Message Digest ...')
        response = requests.request(method='POST', url=apiUrl, headers=header)
        response_data = json.loads(response.text)
        logger.debug(response.status_code, response_data)

        return response_data["d"]["GetContextWebInformation"]["FormDigestValue"].split(",")[0]

    def upload_files(self,folder_name,file_path):
        file_name = file_path.split('/')[-1]
        file_name=file_name.replace("'","''")
        # Read in the file that we are going to upload
        file = open(file_path, 'rb')
        folderUrl = f'/sites/{self.SITE_NAME}/Shared Documents/' + folder_name

        # Sets up the url for requesting a file upload
        requestUrl = f'https://{self.TENANT_URL}/sites/{self.SITE_NAME}/_api/web/getfolderbyserverrelativeurl(\'' + folderUrl + '\')/Files/add(url=\''+file_name+'\',overwrite=true)'

        # Setup the required headers for communicating with SharePoint
        headers = {'Content-Type': 'application/json; odata=verbose', 'accept': 'application/json;odata=verbose',
                   "X-RequestDigest": self.get_message_digest(), "Authorization": "Bearer " + self.TOKEN}

        # Execute the request. If you run into issues, inspect the contents of uploadResult
        uploadResult = requests.request(method='POST', url=requestUrl, data=file.read(), headers=headers)

        return uploadResult

    def get_files_in_folder(self, folder_name):
        apiUrl = f"https://{self.TENANT_URL}/sites/{self.SITE_NAME}/_api/web/GetFolderByServerRelativeUrl('Shared Documents/{folder_name}')/Files"

        header = {
            "Authorization": "Bearer " + self.TOKEN,
            "Accept": "application/json;odata=verbose",
            "Content-Type": "application/json"
        }

        response = requests.request(method='GET', url=apiUrl, headers=header)

        response = json.loads(response.text)['d']['results']

        return response

    def download_file(self, folder_name, file_name):
        apiUrl = f"https://{self.TENANT_URL}/sites/{self.SITE_NAME}/_api/web/GetFolderByServerRelativeUrl('Shared Documents/{folder_name}')/Files('{file_name}')/$value"

        header = {
            "Authorization": "Bearer " + self.TOKEN,
        }

        response = requests.request(method='GET', url=apiUrl, headers=header)

        # Note: bytes are returned, so grab the response in bytes
        return response.content


if __name__ == "__main__":
    sharepoint = Sharepoint()
    # sharepoint.create_folder(os.getenv('RECORDINGS_FOLDER'))
    sharepoint.upload_files(os.getenv('RECORDINGS_FOLDER'),'samples/test.mp4')
    sharepoint.upload_files(os.getenv('RECORDINGS_FOLDER'),"samples/User_Two's_Personal_Room-20221221_1509-1.mp4")