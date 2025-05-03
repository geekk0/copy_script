import os
from typing import AsyncContextManager

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import StreamingResponse
from tortoise import Tortoise
from os import environ
from dotenv import load_dotenv

from enhance_backend.database.db_config import DATABASE_URL
from enhance_backend.routers.clients import clients_router
from enhance_backend.routers.tasks import tasks_router
from enhance_backend.routers.packages import packages_router
from enhance_backend.utils import logger

load_dotenv()

backend_port = environ.get("BACKEND_PORT")


async def lifespan(application: FastAPI) -> AsyncContextManager[None]:
    await init_db()
    yield
    await shutdown()

app = FastAPI(lifespan=lifespan)


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info(f"Запрос: {request.method} {request.url} {request.headers}")

        response = await call_next(request)

        #  ответа
        if isinstance(response, StreamingResponse):
            logger.info(f"Ответ (streaming): {response.status_code} {response.headers}")
        else:
            try:
                logger.info(f"Ответ: {response.status_code} {response.body[:100]}")  # Логируем только часть тела
            except AttributeError:
                logger.info(f"Ответ: {response.status_code} (без тела)")

        return response


app.add_middleware(RequestLoggerMiddleware)


async def init_db():
    await Tortoise.init(
        db_url=DATABASE_URL,
        modules={"models": ["enhance_backend.models"]}
    )
    await Tortoise.generate_schemas()


async def shutdown():
    await Tortoise.close_connections()

app.include_router(clients_router)
app.include_router(tasks_router)
app.include_router(packages_router)

log_folder = os.path.join(os.getcwd(), "logs")
if not os.path.exists(log_folder):
    os.makedirs(log_folder)

if __name__ == "__main__":
    import uvicorn
    backend_port = environ.get("BACKEND_PORT")
    uvicorn.run(app, host="0.0.0.0", port=int(backend_port), access_log=True)
