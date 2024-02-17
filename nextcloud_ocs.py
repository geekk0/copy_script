import requests

from bs4 import BeautifulSoup
from os import environ


class NextcloudOCS:

    csrf_token = None
    server_url = "cloud.reflect-studio.ru"
    username = environ.get('NEXTCLOUD_USERNAME')
    password = environ.get('NEXTCLOUD_PASSWORD')
    response = None
    error = None
    url = None

    def __init__(self):
        pass

    def get_token(self):
        url = f'https://{self.server_url}'
        response = requests.get(url, auth=(self.username, self.password))

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            data_requesttoken = soup.head.get('data-requesttoken')

            self.csrf_token = data_requesttoken

        else:
            print("Failed to retrieve data: HTTP status code", response.status_code)

    def send_request_folder_share(self, path):
        url = f'https://{self.server_url}/ocs/v2.php/apps/files_sharing/api/v1/shares'

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
        except Exception as e:
            self.error = e

    def check_response_errors(self):
        if self.error:
            print(f'ERROR: {self.error}')
            return
        elif self.response.status_code != 200:
            print(f'error: {self.response.text}')
            return
        else:
            return True

    def get_url_from_response(self):
        soup = BeautifulSoup(self.response.text, 'xml')
        url_tag = soup.find('url')
        url_value = url_tag.text if url_tag else None
        self.url = url_value
