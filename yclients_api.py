import datetime
import json
import time

import requests

from os import environ
from dotenv import load_dotenv
from datetime import datetime, timedelta


class YclientsService:
    base_url = 'https://api.yclients.com/api/v1'

    def __init__(self, studio_id):
        load_dotenv()
        self.login = environ.get('YCLIENTS_LOGIN')
        self.password = environ.get('YCLIENTS_PASSWORD')
        self.user_token = environ.get('YCLIENTS_USER_TOKEN')
        self.partner_token = environ.get('YCLIENTS_PARTNER_TOKEN')
        self.company_id = environ.get('YCLIENTS_COMPANY_ID')
        self.response = None
        self.error = None
        self.client_info = None
        self.studio_id = studio_id

    def get_user_token(self):
        url = self.base_url + '/auth'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.partner_token,
            'Accept': 'application/vnd.yclients.v2+json'
        }
        body = {
            'login': self.login,
            'password': self.password
        }

        request = requests.Request(method='POST', url=url, headers=headers, json=body)

        prepared_request = request.prepare()

        try:
            response = requests.Session().send(prepared_request)
            self.error = None
            if response.json().get('data').get('user_token'):
                self.user_token = response.json().get('data').get('user_token')

        except Exception as e:
            self.error = f'get user_token error: {e}'

    def get_appointments_list(self):
        url = self.base_url + '/records/' + self.company_id

        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.partner_token + ', User ' + self.user_token,
            'Accept': 'application/vnd.yclients.v2+json'
        }

        params = {
            'staff_id': self.studio_id,
            'start_date': datetime.now().strftime('%Y-%m-%d'),
            'end_date': datetime.now().strftime('%Y-%m-%d')
        }

        response = requests.get(url, params=params, headers=headers)

        data = response.json().get('data')

        return data

    def get_companies_list(self):
        url = self.base_url + '/companies'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.partner_token + ', User ' + self.user_token,
            'Accept': 'application/vnd.yclients.v2+json'
        }

        response = requests.get(url, headers=headers)

    def get_companies_group(self):
        url = self.base_url + '/groups'

        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.partner_token + ', User ' + self.user_token,
            'Accept': 'application/vnd.yclients.v2+json'
        }

        response = requests.get(url, headers=headers)

    def get_staff_list(self):
        url = self.base_url + '/company/' + self.company_id + '/staff'

        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.partner_token + ', User ' + self.user_token,
            'Accept': 'application/vnd.yclients.v2+json'
        }

        response = requests.get(url, headers=headers)

    @staticmethod
    def get_point_timestamps_from_date(folder_hour_range):
        """Get both start and finish timestamps for the given folder hour range."""
        start_hour_str, finish_hour_str = folder_hour_range.split('-')
        start_hour = int(start_hour_str)
        finish_hour = int(finish_hour_str)

        current_datetime = datetime.now()
        start_datetime = current_datetime.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        finish_datetime = current_datetime.replace(hour=finish_hour, minute=0, second=0, microsecond=0)

        start_timestamp = int(start_datetime.timestamp())
        finish_timestamp = int(finish_datetime.timestamp())

        return start_timestamp, finish_timestamp

    def get_client_info_by_record(self, data, folder_hour_range):
        start_hour = int(folder_hour_range.split('-')[0])
        current_datetime = datetime.now()
        start_datetime = current_datetime.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        searching_datetime_value = start_datetime.strftime("%Y-%m-%d %H:%M:%S")

        start_datetime_half_hour = current_datetime.replace(hour=start_hour, minute=30, second=0, microsecond=0)
        searching_datetime_value_half_hour = start_datetime_half_hour.strftime("%Y-%m-%d %H:%M:%S")

        client_record = [x for x in data if x['date'] == searching_datetime_value
                         or x['date'] == searching_datetime_value_half_hour]

        if client_record[0]:
            client_details_data = client_record[0]['client']
            self.client_info = {
                'client_name': client_details_data['name'],
                'client_id': client_details_data['id'],
                'client_phone_number': client_details_data['phone'],
                'client_email': client_details_data['email'],
            }

    def get_appointed_client_info(self, folder_hour_range):
        data = self.get_appointments_list()
        if data:
            self.get_client_info_by_record(data, folder_hour_range)

    def send_whatsapp_folder_notifications_to_client(self, shared_folder_block):

        client_id = shared_folder_block['client_id']
        client_name = shared_folder_block['client_name']
        folder_url = shared_folder_block['folder_url']

        message_1 = f'''

            Здравствуйте, {client_name}! Это команда студии автопортрета Reflect\nВаши фотографии готовы и доступны для скачивания по ссылке:\n{folder_url}'''

        message_2 = f'''
            Обращаем ваше внимание, что фотографии будут доступны для скачивания только 7 дней,не забудьте их скачать!\nДля того, чтобы сделать близкий портрет, необходимо кадрировать фотографию.\n 
            Это можно сделать в самом телефоне или в приложение Picsart или Peachy 📸
        '''

        message_3 = f'''
            Будем рады обратной связи и вашим отметкам в социальных сетях:\n 
            https://instagram.com/reflect.foto?igshid=MmIzYWVlNDQ5Yg==\n
            Если вам понравилось и вы хотите подарить этот опыт своим близким, то у нас есть подарочный сертификат - заказать можно тут: https://o2881.yclients.com/loyalty
        '''

        messages = {
            'message_1': message_1,
            # 'message_2': message_2,
            # 'message_3': message_3
        }

        for message_name, message_content in messages.items():
            try:
                result = self.send_whatsapp_message(message_content, client_id)
            except Exception as e:
                self.error = e
            time.sleep(20)

    def send_whatsapp_message(self, message, client_id):

        url = self.base_url + '/sms/clients/by_id/' + self.company_id

        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.partner_token + ', User ' + self.user_token,
            'Accept': 'application/vnd.yclients.v2+json'
        }

        body = {
            'client_ids': [client_id],
            'text': message
        }

        response = requests.post(url, headers=headers, data=json.dumps(body))


        return response.status_code

    def send_email_folder_notification_to_client(self, shared_folder_block):
        url = self.base_url + '/email/clients/by_id/' + self.company_id

        message = f'''
        <html style="">

            <div style="text-align:center;width: 75%;margin:auto;border: solid 3px #eece37;border-radius:15px;">
                <div style="margin:5%">
                    <p style="font-size: 16pt">Здравствуйте, <span style="font-weight: bold">
                    {shared_folder_block['client_name']}</span>!</p>
                    Это команда студии автопортрета Reflect, Ваши фотографии готовы и доступны для скачивания 
                    по <a href={shared_folder_block['folder_url']} style="color: #bcab08">ссылке</a><br></br>
                    Вот <a href="https://reflect-studio.ru/howtosavereflect" style="color: #bcab08">здесь</a> 
                    можно прочитать как сохранять фотографии, чтобы не терялось качество<br>
                    <p><a href="https://cloud.reflect-studio.ru/index.php/s/WraTF4ZKXb92xcY" 
                    style="color: #bcab08">Памятка</a> 
                    для скачивания фото с телефона</p>
                    Обращаем ваше внимание, что фотографии будут доступны для скачивания только 7 дней,
                    не забудьте их скачать!<br><br>

                    Для того, чтобы сделать близкий портрет, необходимо кадрировать фотографию. 
                    Это можно сделать в самом телефоне или в приложение Picsart или Peachy 📸<br><br>

                    Будем рады обратной связи и вашим отметкам в социальных сетях:<br>
                    <a href="https://instagram.com/reflect.foto?igshid=MmIzYWVlNDQ5Yg=="
                    style="color: #bcab08">Instagram</a>
                    <a href="https://yandex.ru/profile/152194276958" 
                    style="color: #bcab08">Яндекс</a>
                    <br><br>

                    Если вам понравилось и вы хотите подарить этот опыт своим близким, то у нас есть подарочный 
                    сертификат - заказать можно <a href="https://o2881.yclients.com/loyalty" 
                    style="color: #bcab08">тут</a><br><br>

                    <div style="width:50%;margin-left: auto;margin-right: auto">
                        <img style="width:35%" src="https://cloud.reflect-studio.ru/index.php/avatar/reflect/512/dark?v=1">
                    </div>
                </div>

            </div>

        </html>
        '''

        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.partner_token + ', User ' + self.user_token,
            'Accept': 'application/vnd.yclients.v2+json'
        }

        body = {
            'client_ids': [shared_folder_block['client_id']],
            'subject': "Ваши фотографии доступны для скачивания",
            'text': message
        }

        response = requests.post(url, headers=headers, data=json.dumps(body))

    def get_clients_list(self):
        url = self.base_url + '/company/' + self.company_id + '/clients/search'

        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.partner_token + ', User ' + self.user_token,
            'Accept': 'application/vnd.yclients.v2+json'
        }

        body = {
            "page": 148,
            'fields': ["id", "name"],

        }

        response = requests.post(url, headers=headers, data=json.dumps(body))

    def get_transactions_list(self, yesterday=None):
        url = self.base_url + '/storages/' + 'transactions/' + self.company_id

        yesterday = datetime.now() - timedelta(days=1)

        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.partner_token + ', User ' + self.user_token,
            'Accept': 'application/vnd.yclients.v2+json'
        }

        params = {
            'count': 100
        }

        if yesterday:
            params['start_date']= yesterday.strftime('%Y-%m-%d')
            params['end_date'] = yesterday.strftime('%Y-%m-%d')

        request = requests.Request(method='GET', url=url, headers=headers, params=params)
        prepared_request = request.prepare()
        session = requests.Session()

        response = session.send(prepared_request)

        return response

    def get_clients_info(self, clients_ids: list = None):
        url = self.base_url + '/company/' + self.company_id + '/clients/search'

        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.partner_token + ', User ' + self.user_token,
            'Accept': 'application/vnd.yclients.v2+json'
        }

        body = {}

        if clients_ids:
            body = {
                "fields": ["id","name", "email"],
                "filters": [
                    {
                        "type": "id",
                        "state":
                        {
                            "value": clients_ids
                        }
                    }
                ]
            }

        response = requests.post(url, headers=headers, data=json.dumps(body))

        return response

    def get_client_certificate(self, client_phone):
        url = self.base_url + '/loyalty/certificates/'

        params = {
            'company_id': self.company_id,
            'phone': client_phone
        }

        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.partner_token + ', User ' + self.user_token,
            'Accept': 'application/vnd.yclients.v2+json'
        }

        response = requests.get(url, params=params, headers=headers)

        return response

