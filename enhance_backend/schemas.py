from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from tortoise.contrib.pydantic import pydantic_model_creator

from enhance_backend.models import EnhanceTask, StatusEnum, Package, Order


class ClientRequest(BaseModel):
    chat_id: int
    yclients_id: int
    phone_number: str
    username: Optional[str] = None

    class Config:
        from_attributes = True


class ClientResponse(ClientRequest):
    id: int


class EnhanceTaskRequest(BaseModel):
    client_chat_id: int
    folder_path: str
    yclients_record_id: int
    files_list: list[str]
    yclients_certificate_code: int | None = None
    yclients_certificate_type_id: int | None = None
    max_photo_amount: int | None = None
    price: int | None = None


EnhanceTaskResponse = pydantic_model_creator(
    EnhanceTask,
    name="EnhanceTaskResponse",
    exclude=("client", "package")
)

# PackageRequest = pydantic_model_creator(Package, exclude=("id",))


# class PackageRequest(BaseModel):
#     name: str
#     photos_number: int
#     price: int
#     yclients_certificate_type_id: int
#     purchase_url: str
#     published: bool


# class PackageResponse(BaseModel):
#     name: str
#     photos_number: int
#     price: int
#     yclients_certificate_type_id: int
#     purchase_url: str
#     published: bool

PackageResponse = pydantic_model_creator(Package)

# OrderRequest = pydantic_model_creator(
#     Order,
#     name="OrderRequest",
#     exclude=("id", "created_at", "updated_at")
# )
# OrderResponse = pydantic_model_creator(Order)


class EnhanceTaskResponseWithDetails(BaseModel):
    id: int
    client: ClientRequest
    folder_path: str
    yclients_record_id: int
    status: StatusEnum
    created_at: str
    enhanced_files_count: int
    files_list: Optional[list[str]]
    yclients_certificate_code: Optional[str]
    max_photo_amount: Optional[int]

    class Config:
        from_attributes = True


class EnhanceTaskUpdate(BaseModel):
    folder_path: str | None = None
    status: StatusEnum | None = None
    enhanced_files_count: int | None = None
    files_list: list[str] | None = None


