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

    @staticmethod
    async def remove_client(chat_id: int):
        client = await Client.get_or_none(chat_id=chat_id)
        if client:
            await client.delete()

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

    async def add_enhance_task(
            self, client_chat_id: int, folder_path: str,
            yclients_record_id: int, files_list: list = None
    ):
        client = await Client.get(chat_id=client_chat_id)
        task = await EnhanceTask.create(
            client=client, folder_path=folder_path,
            yclients_record_id=yclients_record_id,
            files_list=files_list
        )
        return task

    async def get_enhance_tasks_by_client(self, client_id: int):
        """
        Получает все задачи на улучшение для клиента.
        Возвращает список задач.
        """
        tasks = await EnhanceTask.filter(client_id=client_id)
        return tasks
