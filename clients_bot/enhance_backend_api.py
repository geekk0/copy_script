import httpx
from dotenv import load_dotenv

from bot_setup import logger
from os import environ

load_dotenv()


class EnhanceBackendAPI:
    def __init__(self):
        self.backend_port = str(environ.get("BACKEND_PORT"))
        self.base_url = f"http://127.0.0.1:{self.backend_port}"
        self.client = httpx.AsyncClient()

    async def send_request(self, method: str, endpoint: str, params=None,
                           json=None, data=None, headers=None):
        url = f"{self.base_url}{endpoint}"
        logger.info(f"Отправка {method} запроса на {url} с параметрами: "
                     f"{params}, телом: {json or data}")

        response = await self.client.request(
            method, url, params=params, json=json, data=data, headers=headers
        )
        response.raise_for_status()
        logger.info(f"Ответ: {response.status_code} - {response.text}")
        return response

    async def close(self):
        await self.client.aclose()

    async def get_user_by_chat_id(self, chat_id: int):
        method = "GET"
        endpoint = "/clients"
        params = {"client_chat_id": chat_id}
        try:
            response = await self.send_request(method, endpoint, params)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                return False
        except Exception as e:
            if e.status_code != 404:
                logger.error(f"Произошла ошибка в get_user_by_chat_id: {e}")
            return False

    async def add_client(self, client_data: dict):
        method = "POST"
        endpoint = "/clients"
        try:
            response = await self.send_request(method, endpoint, json=client_data)
            return response.json()
        except Exception as e:
            logger.error(f"Произошла ошибка в add_client: {e}")
            return False

    async def remove_client(self, client_id: int):
        method = "DELETE"
        endpoint = "/clients"
        try:
            response = await self.send_request(method, endpoint, params={"client_chat_id": client_id})
            return response
        except Exception as e:
            logger.error(f"Произошла ошибка в add_client: {e}")
            return False

    async def get_client_tasks(self, client_id: int):
        method = "GET"
        endpoint = "/tasks"
        try:
            response = await self.send_request(method, endpoint, params={"client_id": client_id})
            return response.json()
        except Exception as e:
            logger.error(f"Произошла ошибка в add_client: {e}")
            return False

    async def add_enhance_task(self, task_data: dict):
        method = "POST"
        endpoint = "/tasks"
        try:
            response = await self.send_request(method, endpoint, json=task_data)
            if response.status_code == 201 or 200:
                return response.json()
            return False
        except Exception as e:
            logger.error(f"Произошла ошибка в add_task: {e}")
            return False

    async def update_enhance_task(self, task_id: int, task_data: dict):
        method = "PATCH"
        endpoint = "/tasks"
        try:
            response = await self.send_request(
                method, endpoint,
                params={"task_id": task_id},
                json=task_data
            )
            return response
        except Exception as e:
            logger.error(f"Произошла ошибка в update_enhance_task: {e}")
            return False

    async def change_task_status(self, folder, status):
        method = "PATCH"
        endpoint = f"/tasks/status"
        params = {"folder_path": folder, "status": status}
        try:
            response = await self.send_request(method, endpoint, params=params)
            return response.json()
        except Exception as e:
            logger.error(f"Произошла ошибка в change_task_status: {e}")
            return False

    # async def call_backend_completed(self, folder):
    #     method = "POST"
    #     endpoint = f"/tasks/completed"
    #     body = {"folder": folder}
    #     try:
    #         response = await self.send_request(method, endpoint, json=body)
    #         return response.json()
    #     except Exception as e:
    #         logger.error(f"Произошла ошибка в update_task: {e}")
    #         return False
