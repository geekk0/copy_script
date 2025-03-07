import logging
import subprocess

import httpx

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from tortoise.exceptions import DoesNotExist
from os import environ

from enhance_backend.models import StatusEnum
from enhance_backend.schemas import EnhanceTaskResponse, EnhanceTaskRequest, \
    EnhanceTaskUpdate
from enhance_backend.db_manager import DatabaseManager
from enhance_backend.notifications import ClientsBot
from clients_bot.utils import remove_demo_folder

tasks_router = APIRouter(prefix="/tasks")

db_manager = DatabaseManager()
load_dotenv()

@tasks_router.get("")
async def get_enhance_tasks_by_client(client_id: int)\
        -> list[EnhanceTaskResponse]:
    try:
        tasks = await db_manager.get_clients_enhance_tasks(client_id)
        return [EnhanceTaskResponse.model_validate(task, from_attributes=True)
                for task in tasks]

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Client not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@tasks_router.post("")
async def add_task(task_data: EnhanceTaskRequest) -> EnhanceTaskResponse:
    try:
        task = await db_manager.add_enhance_task(task_data.client_chat_id, task_data)
        return task
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Client not found")
    except Exception as e:
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
        raise HTTPException(status_code=500, detail=str(e))


@tasks_router.patch("/status")
async def change_task_status(folder_path: str, status: str):
    try:
        task_folder_path = folder_path.replace('_demo', '')
        status_enum = getattr(StatusEnum, status.upper(), None)
        if status_enum is None:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        tasks_found_by_folder = await db_manager.search_enhance_tasks_by_folder(task_folder_path)
        print(f"tasks_found_by_folder: {tasks_found_by_folder}")
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
        raise HTTPException(status_code=500, detail=str(e))


@tasks_router.delete("")
async def remove_task(task_id: int) -> dict[str, str]:
    try:
        await db_manager.remove_enhance_task(task_id)
        return {"message": "Task removed successfully"}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@tasks_router.post("/completed")
async def task_is_completed(folder_dict: dict[str, str]) -> None:
    folder_path = folder_dict.get("folder")
    try:
        task_folder_path = folder_path.replace('_demo', '')
        tasks_found_by_folder = await db_manager.search_enhance_tasks_by_folder(task_folder_path)
        print(f"tasks_found_by_folder: {tasks_found_by_folder}")
        if len(tasks_found_by_folder) == 0:
            return
        else:
            found_task = tasks_found_by_folder[0]

        await found_task.fetch_related("client")
        client = found_task.client
        print(f"client id: {client.id}")
        task_update_data = (
            EnhanceTaskUpdate(status=StatusEnum.COMPLETED).model_dump(exclude_unset=True)
        )
        await db_manager.update_enhance_task(found_task.id, task_update_data)

        folder_link = await share_folder(found_task.folder_path)

        clients_bot = ClientsBot()
        print(f"chat_id: {client.chat_id}")
        text = f"Ваша папка обработана"
        if folder_link:
            text += f"\nссылка на скачивание: {folder_link}"
        await clients_bot.send_notification(client.chat_id, text)
        await remove_demo_folder(folder_dict.get("folder"))

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def share_folder(folder_path: str) -> str:
    try:
        actual_folder_path = folder_path.replace('/cloud/reflect/files', '')
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

        if response.status_code == 200:
            share_info = response.json()
            share_url = share_info['ocs']['data']['url']
            return share_url
        else:
            logging.error(f"Произошла ошибка в share_folder: "
                          f"{response.status_code}, {response.text}")
    except Exception as e:
        logging.error(f"Произошла ошибка в share_folder: {e}")

