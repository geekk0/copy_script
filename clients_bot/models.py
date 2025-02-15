from tortoise import Tortoise, fields, models
from enum import Enum
from pydantic import BaseModel


class StatusEnum(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    PROCESSING = "processing"


class Client(models.Model):
    id = fields.IntField(pk=True)
    chat_id = fields.BigIntField(unique=True)
    yclients_id = fields.BigIntField(unique=True)
    phone_number = fields.TextField()
    username = fields.TextField(null=True)


class Order(models.Model):
    id = fields.IntField(pk=True)
    client = fields.ForeignKeyField(
        'models.Client', related_name='orders', on_delete=fields.CASCADE)
    photo_path = fields.TextField()
    status = fields.CharEnumField(StatusEnum, default=StatusEnum.PENDING)
    created_at = fields.DatetimeField(auto_now_add=True)


class EnhanceTask(models.Model):
    id = fields.IntField(pk=True)
    client = fields.ForeignKeyField(
        'models.Client', related_name='enhance_tasks', on_delete=fields.CASCADE)
    folder_path = fields.TextField()
    yclients_record_id = fields.BigIntField(unique=True)
    status = fields.CharEnumField(StatusEnum, default=StatusEnum.PENDING)
    created_at = fields.DatetimeField(auto_now_add=True)
    enhanced_files_count = fields.IntField(default=0)
    files_list = fields.JSONField(null=True)


class Record(BaseModel):
    record_id: int
    date: str
    studio: str
