import os
from typing import AsyncContextManager

from fastapi import FastAPI
from tortoise import Tortoise
from os import environ
from dotenv import load_dotenv

from enhance_backend.database.db_config import DATABASE_URL
from enhance_backend.routers.clients import clients_router
from enhance_backend.routers.tasks import tasks_router
from enhance_backend.routers.packages import packages_router

load_dotenv()

backend_port = environ.get("BACKEND_PORT")


async def lifespan(application: FastAPI) -> AsyncContextManager[None]:
    await init_db()
    yield
    await shutdown()

app = FastAPI(lifespan=lifespan)


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
    access_log = True
    uvicorn.run(app, host="0.0.0.0", port=int(backend_port))
