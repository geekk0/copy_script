import os
from typing import AsyncContextManager

from fastapi import FastAPI
from tortoise import Tortoise
from os import environ
from dotenv import load_dotenv

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

current_dir = os.path.dirname(os.path.abspath(__file__))
print(current_dir)
db_path = os.path.join(current_dir, 'database', 'main.db')


async def init_db():
    await Tortoise.init(
        db_url=f"sqlite:///{db_path}",
        modules={"models": ["enhance_backend.models"]}
    )
    await Tortoise.generate_schemas()


async def shutdown():
    await Tortoise.close_connections()

app.include_router(clients_router)
app.include_router(tasks_router)
app.include_router(packages_router)


if __name__ == "__main__":
    import uvicorn
    backend_port = environ.get("BACKEND_PORT")
    print(f"backend_port: {backend_port}")
    uvicorn.run(app, host="0.0.0.0", port=int(backend_port))
