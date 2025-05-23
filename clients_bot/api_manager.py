import httpx

from typing import Optional, Dict, Any
from os import environ
from dotenv import load_dotenv
from clients_bot.bot_setup import logger


class YClientsAPIManager:
    BASE_URL = "https://api.yclients.com/api/v1"

    def __init__(self):
        load_dotenv()
        self.access_token = environ.get("YCLIENTS_USER_TOKEN")
        self.partner_token = environ.get('YCLIENTS_PARTNER_TOKEN')
        self.company_id = environ.get('YCLIENTS_COMPANY_ID')
        self.headers = {
            "Authorization": 'Bearer ' + self.partner_token + ', User ' + self.access_token,
            'Accept': 'application/vnd.yclients.v2+json',
            "Content-Type": "application/json"
        }

    async def get_client_info_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}/company/{self.company_id}/clients/search"
        body = {
            "fields": [

                "id",
                "name",
                "email",
            ],
            "filters": [
                {
                    "type": "quick_search",
                    "state":

                        {
                            "value": f"{phone}"
                        }

                }
            ]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=body, timeout=20)

        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return None

    async def get_client_records_by_client_id(self, client_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}/records/{self.company_id}"
        params = {"client_id": client_id}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, params=params)

        data = response.json()

        if response.status_code == 200:
            return data
        else:
            return None

    async def create_client(self, client_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Создаёт нового клиента.
        """
        url = f"{self.BASE_URL}/clients/{self.company_id}"

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=client_data)

        if response.status_code in [200, 201]:
            return response.json()
        else:
            return None

    async def get_enhance_certs(self, phone: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}/loyalty/certificates/"
        params = {
            "company_id": self.company_id,
            "phone": phone
        }

        logger.debug(f"get certs url: {url}")

        async with httpx.AsyncClient() as client:

            response = await client.get(url, headers=self.headers, params=params)

            req = response.request

            logger.debug(f"Request method: {req.method}")
            logger.debug(f"Request URL: {req.url}")
            logger.debug(f"Request headers: {req.headers}")
            logger.debug(f"Request content: {req.content.decode(errors='ignore')}")

        if response.status_code == 200:
            data = response.json()
            logger.debug(f"certs response: {data}")
            return data
        else:
            print(f"Ошибка {response.status_code}: {response.text}")
            return None