from tortoise import Tortoise, fields, models
from enum import Enum
from pydantic import BaseModel


class StatusEnum(str, Enum):
    PENDING = "Задача создана"
    QUEUED = "Обработка добавлена в очередь"
    PROCESSING = "Идет обработка"
    COMPLETED = "Обработка завершена"
    FAILED = "Ошибка обработки"


class Client(models.Model):
    id = fields.IntField(pk=True)
    chat_id = fields.BigIntField(unique=True)
    yclients_id = fields.BigIntField(unique=True)
    phone_number = fields.TextField()
    username = fields.TextField(null=True)

    class Meta:
        table = "clients"


class Package(models.Model):

    id = fields.IntField(pk=True)
    name = fields.TextField()
    photos_number = fields.IntField()
    price = fields.IntField()
    published = fields.BooleanField(default=False)
    yclients_certificate_type_id = fields.IntField()
    purchase_url = fields.TextField(null=True)

    class Meta:
        table = "packages"


class Order(models.Model):
    id = fields.IntField(pk=True)
    client = fields.ForeignKeyField(
        'models.Client', related_name='orders', on_delete=fields.CASCADE)
    photo_path = fields.TextField()
    status = fields.CharEnumField(StatusEnum, default=StatusEnum.PENDING)
    yclients_certificate_type_id = fields.IntField(null=True, default=None)
    yclients_certificate_code = fields.IntField(null=True, default=None)
    amount = fields.IntField(null=True, default=None)
    created_at = fields.DatetimeField(auto_now_add=True)
    package = fields.ForeignKeyField(
        'models.Package', related_name='orders', on_delete=fields.CASCADE
    )

    class Meta:
        table = "orders"


class EnhanceTask(models.Model):
    id = fields.IntField(pk=True)
    client = fields.ForeignKeyField(
        'models.Client', related_name='enhance_tasks', on_delete=fields.CASCADE)
    folder_path = fields.TextField()
    yclients_record_id = fields.BigIntField(null=True, default=None)
    status = fields.CharEnumField(StatusEnum, default=StatusEnum.PENDING)
    created_at = fields.DatetimeField(auto_now_add=True)
    enhanced_files_count = fields.IntField(default=0)
    files_list = fields.JSONField(default=list)
    yclients_certificate_code = fields.CharField(max_length=100, null=True, default=None)
    yclients_certificate_type_id = fields.IntField(null=True, default=None)
    max_photo_amount = fields.IntField(null=True, default=None)
    price = fields.IntField()
    selected_action = fields.TextField(null=True, default=None)

    class Meta:
        table = "enhancetasks"


class Record(BaseModel):
    record_id: int
    date: str
    studio: str
