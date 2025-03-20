from datetime import datetime
from typing import Optional, Any
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
    files_list: list[str]
    package_id: int


EnhanceTaskResponse = pydantic_model_creator(
    EnhanceTask,
    name="EnhanceTaskResponse",
    exclude=("client", "package")
)

PackageRequest = pydantic_model_creator(Package, exclude=("id",))
PackageResponse = pydantic_model_creator(Package)


class EnhanceTaskResponseWithDetails(BaseModel):
    id: int
    client: ClientRequest
    folder_path: str
    yclients_record_id: int
    status: StatusEnum
    created_at: str
    enhanced_files_count: int
    files_list: Optional[list[str]]
    package: PackageResponse

    class Config:
        orm_mode = True
        from_attributes = True


class EnhanceTaskUpdate(BaseModel):
    folder_path: str | None = None
    status: StatusEnum | None = None
    enhanced_files_count: int | None = None
    files_list: list[str] | None = None


