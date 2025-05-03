import logging
import subprocess

import httpx

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.exceptions import DoesNotExist
from os import environ
from bs4 import BeautifulSoup


from enhance_backend.models import StatusEnum, Client, Package
from enhance_backend.schemas import EnhanceTaskResponse, EnhanceTaskRequest, \
    EnhanceTaskUpdate, EnhanceTaskResponseWithDetails, ClientResponse
from enhance_backend.db_manager import DatabaseManager
from enhance_backend.notifications import ClientsBot
from clients_bot.utils import remove_task_folder
from enhance_backend.utils import logger

tasks_router = APIRouter(prefix="/tasks")

db_manager = DatabaseManager()
load_dotenv()


@tasks_router.get("")
async def get_clients_enhance_tasks(client_id: int, yclients_records_id: int)\
        -> list[EnhanceTaskResponseWithDetails]:
    try:
        tasks = await db_manager.get_clients_enhance_tasks(client_id, yclients_records_id)
        result = [
            EnhanceTaskResponseWithDetails(
                id=task.id,
                client=ClientResponse.model_validate(task.client, from_attributes=True),
                folder_path=task.folder_path,
                yclients_record_id=task.yclients_record_id,
                status=task.status,
                created_at=task.created_at.isoformat(),
                enhanced_files_count=task.enhanced_files_count,
                files_list=task.files_list or [],
                yclients_certificate_code=task.yclients_certificate_code,
                max_photo_amount=task.max_photo_amount,
            )
            for task in tasks
        ]
        return result

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Client not found")
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))


@tasks_router.post("")
async def add_task(task_data: EnhanceTaskRequest) -> EnhanceTaskResponse:
    try:
        task = await db_manager.add_enhance_task(task_data.client_chat_id, task_data)
        return task
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Client not found")
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))


@tasks_router.patch("")
async def update_task(task_id: int, task_data: EnhanceTaskUpdate) -> EnhanceTaskResponse:
    try:
        update_data = task_data.model_dump(exclude_unset=True)
        task = await db_manager.update_enhance_task(task_id, update_data)
        return EnhanceTaskResponse.model_validate(task)
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))


@tasks_router.patch("/status")
async def change_task_status(folder_path: str, status: str):
    try:
        task_folder_path = folder_path.replace('_task', '')
        tasks_found_by_folder = await db_manager.search_enhance_tasks_by_folder(task_folder_path)
        logger.debug(f"tasks_found_by_folder: {tasks_found_by_folder}")
        status_enum = StatusEnum[status].value
        if not tasks_found_by_folder:
            return
        else:
            found_task = tasks_found_by_folder[0]
        task_update_data = (
            EnhanceTaskUpdate(status=status_enum).model_dump(exclude_unset=True)
        )
        await db_manager.update_enhance_task(found_task.id, task_update_data)
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))


@tasks_router.delete("")
async def remove_task(task_id: int) -> dict[str, str]:
    try:
        await db_manager.remove_enhance_task(task_id)
        return {"message": "Task removed successfully"}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))


@tasks_router.post("/completed")
async def task_is_completed(folder_dict: dict[str, str]) -> None:
    folder_path = folder_dict.get("folder")
    try:
        task_folder_path = folder_path.replace('_task', '')
        tasks_found_by_folder = await db_manager.search_enhance_tasks_by_folder(task_folder_path)
        logger.debug(f"tasks_found_by_folder: {tasks_found_by_folder}")
        if len(tasks_found_by_folder) == 0:
            return
        else:
            found_task = tasks_found_by_folder[0]

        await found_task.fetch_related("client")
        client = found_task.client
        logger.debug(f"client id: {client.id}")
        task_update_data = (
            EnhanceTaskUpdate(status=StatusEnum.COMPLETED).model_dump(exclude_unset=True)
        )
        await db_manager.update_enhance_task(found_task.id, task_update_data)

        folder_link = await share_folder(folder_path + "_AI")
        logger.debug(f"folder_link: {folder_link}")

        clients_bot = ClientsBot()
        logger.debug(f"chat_id: {client.chat_id}")
        text = f"Ваша папка обработана"
        if folder_link:
            text += f"\nссылка на скачивание:\n{folder_link}"
        await clients_bot.send_notification(client.chat_id, text)
        await remove_task_folder(folder_dict.get("folder"))

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))


async def share_folder(folder_path: str) -> str:
    try:
        actual_folder_path = folder_path.replace('/cloud/reflect/files/', '')
        url = "https://cloud.reflect-studio.ru/ocs/v2.php/apps/files_sharing/api/v1/shares"
        body = {
            "path": actual_folder_path,
            "shareType": "3",
            "permissions": "1"
        }
        headers = {
            "OCS-APIRequest": "true"
        }
        username = environ.get('NEXTCLOUD_USERNAME')
        password = environ.get('NEXTCLOUD_PASSWORD')
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data=body,
                headers=headers,
                auth=(username, password)
            )

            if response.status_code != 200:
                logging.error(f"Ошибка запроса: {response.status_code}, текст: {response.text}")
                return ""

            soup = BeautifulSoup(response.text, "lxml-xml")
            link = soup.find("url")  # Ищем тег <url> в XML

            if link:
                folder_link = link.text.strip()  # Получаем только текст из тега <url>
                logger.debug(f"folder_link: {folder_link}")  # Печатаем чистую ссылку
                return folder_link
            else:
                logging.error("URL не найден в ответе сервера")
                return ""
    except Exception as e:
        logger.error(f"Произошла ошибка в share_folder: {e}")
