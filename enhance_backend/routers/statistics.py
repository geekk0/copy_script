import logging
import httpx

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

from enhance_backend.db_manager import DatabaseManager
from enhance_backend.models import EnhanceTask, Client
from enhance_backend.schemas import StatusEnum, EnhanceTaskResponseWithDetails, ClientResponse
from tortoise.functions import Count

stats_router = APIRouter(prefix="/statistics")

db_manager = DatabaseManager()
load_dotenv()


@stats_router.get("/tasks")
async def get_count_tasks():
    try:
        # Статистика по статусам
        query = (
            EnhanceTask
            .all()
            .group_by("status")
            .annotate(count=Count("id"))
            .values("status", "count")
        )
        rows = await query

        status_counts = {row["status"]: row["count"] for row in rows}

        full_result = {
            status.value: status_counts.get(status.value, 0)
            for status in StatusEnum
        }

        latest_tasks = await EnhanceTask.all().prefetch_related("client").order_by("-created_at").limit(3)

        latest_result = [
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
                selected_action=task.selected_action
            )
            for task in latest_tasks
        ]

        return {
            "status_summary": full_result,
            "latest_tasks": latest_result
        }

    except Exception as e:
        logging.error(e)
        raise HTTPException(status_code=500, detail=str(e))


@stats_router.get("/clients")
async def get_clients_stats():
    try:
        # Общее количество клиентов
        total_clients = await Client.all().count()

        # Последние 3 зарегистрированных клиента (по id или по created_at, если добавишь)
        latest_clients = await Client.all().order_by("-id").limit(3)

        # Сериализация (можно подставить свою модель ответа при необходимости)
        latest_result = [
            {
                "id": client.id,
                "chat_id": client.chat_id,
                "yclients_id": client.yclients_id,
                "phone_number": client.phone_number,
                "username": client.username,
            }
            for client in latest_clients
        ]

        return {
            "total_clients": total_clients,
            "latest_clients": latest_result
        }

    except Exception as e:
        logging.error(e)
        raise HTTPException(status_code=500, detail=str(e))
