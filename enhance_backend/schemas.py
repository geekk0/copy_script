from typing import Optional
from pydantic import BaseModel, Field
from tortoise.contrib.pydantic import pydantic_model_creator

from enhance_backend.models import EnhanceTask, StatusEnum, Package


class ClientRequest(BaseModel):
    chat_id: int
    yclients_id: int
    phone_number: str
    username: Optional[str] = None

    class Config:
        orm_mode = True
        from_attributes = True


class ClientResponse(ClientRequest):
    id: int


class EnhanceTaskRequest(BaseModel):
    client_chat_id: int
    folder_path: str
    yclients_record_id: int
    files_list: list
    package_id: int


EnhanceTaskResponse = pydantic_model_creator(EnhanceTask) # , include=('client', 'package')


class EnhanceTaskUpdate(BaseModel):
    folder_path: str | None = None
    status: StatusEnum | None = None
    enhanced_files_count: int | None = None
    files_list: list | None = None


PackageRequest = pydantic_model_creator(Package, exclude=("id",))
PackageResponse = pydantic_model_creator(Package)

