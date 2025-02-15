from tortoise import Tortoise
from clients_bot.models import Client, Order, EnhanceTask
from tortoise.exceptions import DoesNotExist


class DatabaseManager:
    async def add_client(self, chat_id: int,
                         phone_number: str, yclients_id: int):
        client = await Client.create(
            chat_id=chat_id,
            phone_number=phone_number,
            yclients_id=yclients_id
        )
        return client

    async def get_client_by_chat_id(self, chat_id: int):
        """
        Ищет клиента по chat_id.
        Возвращает объект Client, если найден, или None, если нет.
        """
        try:
            client = await Client.get(chat_id=chat_id)
            return client
        except DoesNotExist:
            return None

    async def add_order(self, client_id: int, photo_path: str, status: str):
        client = await Client.get(id=client_id)
        order = await Order.create(client=client, photo_path=photo_path, status=status)
        return order

    async def get_orders_by_client(self, client_id: int):
        """
        Получает все заказы для клиента.
        Возвращает список заказов.
        """
        orders = await Order.filter(client_id=client_id)
        return orders

    async def add_enhance_task(self, client_chat_id: int, folder_path: str, yclients_record_id: int):
        client = await Client.get(chat_id=client_chat_id)
        task = await EnhanceTask.create(
            client=client, folder_path=folder_path,
            yclients_record_id=yclients_record_id)
        return task

    async def get_enhance_tasks_by_client(self, client_id: int):
        """
        Получает все задачи на улучшение для клиента.
        Возвращает список задач.
        """
        tasks = await EnhanceTask.filter(client_id=client_id)
        return tasks
