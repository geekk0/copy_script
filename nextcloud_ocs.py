import requests

from bs4 import BeautifulSoup
from os import environ
from dotenv import load_dotenv


class NextcloudOCS:

    csrf_token = None
    server_domain = "cloud.reflect-studio.ru"
    username = None
    password = None
    response = None
    error = None
    shared_folder_url = None

    def __init__(self):
        load_dotenv()
        self.username = environ.get('NEXTCLOUD_USERNAME')  
        self.password = environ.get('NEXTCLOUD_PASSWORD')

    def get_token(self):
        url = f'https://{self.server_domain}'

        try:
            response = requests.get(url, auth=(self.username, self.password))
            self.response = response
        except Exception as e:
            self.error = f'error while send token request: {e}'
            return

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            data_requesttoken = soup.head.get('data-requesttoken')

            self.csrf_token = data_requesttoken
            self.error = None

        else:
            self.error = f'send token response error: {response.status_code}'

    def send_request_folder_share(self, path):
        url = f'https://{self.server_domain}/ocs/v2.php/apps/files_sharing/api/v1/shares'

        headers = {
            'X-CSRF-Token': self.csrf_token,
            'OCS-APIRequest': 'true',
        }

        data = {
            'path': path,
            'shareType': '3',
            'permissions': '1'
        }

        request = requests.Request('POST', url=url,
                                   headers=headers,
                                   data=data,
                                   auth=(self.username, self.password))

        prepared_request = request.prepare()

        try:
            response = requests.Session().send(prepared_request)
            self.response = response
            self.error = None
        except Exception as e:
            self.error = f'send_request_folder_share error: {e}'

    def get_url_from_response(self):
        soup = BeautifulSoup(self.response.text, 'xml')
        url_tag = soup.find('url')
        url_value = url_tag.text if url_tag else None
        self.shared_folder_url = url_value
