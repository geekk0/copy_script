from fastapi import HTTPException
# from requests.packages import package

from enhance_backend.models import Client, Order, EnhanceTask, Package
from tortoise.exceptions import DoesNotExist
from enhance_backend.utils import logger

from enhance_backend.schemas import ClientRequest, ClientResponse, EnhanceTaskResponse


class DatabaseManager:
    @staticmethod
    async def add_client(client_data: ClientRequest) -> ClientResponse:
        client = await Client.create(
            chat_id=client_data.chat_id,
            phone_number=client_data.phone_number,
            yclients_id=client_data.yclients_id,
            username=client_data.username
        )
        return ClientResponse.model_validate(client)

    @staticmethod
    async def remove_client(chat_id: int):
        client = await Client.get_or_none(chat_id=chat_id)
        if client:
            await client.delete()

    @staticmethod
    async def update_client(client_chat_id: int, client_data: ClientRequest) -> Client:
        try:
            client = await Client.get_or_none(chat_id=client_chat_id)
            if not client:
                raise HTTPException(status_code=404, detail="Client not found")

            await client.update_from_dict(client_data.dict(exclude_unset=True))
            await client.save()

            return client
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def get_client_by_chat_id(chat_id: int) -> ClientResponse | None:
        try:
            client = await Client.get_or_none(chat_id=chat_id)
            logger.debug(f"client: {client}")
            return ClientResponse.model_validate(client) if client else None
        except Exception as e:
            logger.error(f"Error while fetching client: {e}")

    @staticmethod
    async def get_all_clients() -> list[ClientResponse]:
        try:
            clients = await Client.all()
            return [ClientResponse.model_validate(client)
                    for client in clients]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def add_order(client_id: int, photo_path: str, status: str):
        client = await Client.get(id=client_id)
        order = await Order.create(client=client, photo_path=photo_path, status=status)
        return order

    @staticmethod
    async def get_orders_by_client(client_id: int):
        """
        Получает все заказы для клиента.
        Возвращает список заказов.
        """
        orders = await Order.filter(client_id=client_id)
        return orders

    @staticmethod
    async def get_enhance_task_by_id(task_id: int):
        task = await EnhanceTask.get_or_none(id=task_id)
        return task

    @staticmethod
    async def search_enhance_tasks_by_folder(folder):
        tasks = await EnhanceTask.filter(folder_path=folder)
        return tasks

    @staticmethod
    async def get_enhance_tasks_by_client(client_id: int):
        tasks = await EnhanceTask.filter(client_id=client_id)
        return tasks

    @staticmethod
    async def add_enhance_task(
            client_chat_id: int,
            task_data: EnhanceTaskResponse
    ) -> EnhanceTaskResponse:
        client = await Client.get(chat_id=client_chat_id)
        task = await EnhanceTask.create(
            client=client,
            folder_path=task_data.folder_path,
            yclients_record_id=task_data.yclients_record_id,
            files_list=task_data.files_list,
            price=task_data.price,
            max_photo_amount=task_data.max_photo_amount,
            yclients_certificate_code=task_data.yclients_certificate_code,
            selected_action=task_data.selected_action
        )
        return EnhanceTaskResponse.model_validate(task)

    @staticmethod
    async def get_clients_enhance_tasks(
            client_id: int) -> list[EnhanceTask]:
        client = await Client.get(id=client_id)
        return await EnhanceTask.filter(
            client_id=client.id,
        ).select_related('client')

    @staticmethod
    async def get_demo_enhance_task(cert_number, folder_path):
        return await EnhanceTask.get(
            yclients_certificate_code=cert_number,
            price=0,
            folder_path=folder_path
        )

    @staticmethod
    async def get_regular_enhance_task(cert_number, folder_path):
        return await EnhanceTask.get(
            yclients_certificate_code=cert_number,
            price__not=0,
            folder_path=folder_path
    )

    @staticmethod
    async def update_enhance_task(task_id: int, task_data: EnhanceTaskResponse) -> EnhanceTask:
        try:
            task = await EnhanceTask.get_or_none(id=task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            await task.update_from_dict(task_data)
            await task.save()

            return task
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def remove_enhance_task(task_id: int):
        task = await EnhanceTask.get_or_none(id=task_id)
        if task:
            await task.delete()

    # @staticmethod
    # async def add_package(package_data: PackageResponse) -> Package:
    #     package = await Package.create(
    #         name=package_data.name,
    #         photos_number=package_data.photos_number,
    #         price=package_data.price
    #     )
    #     return package
    #
    # @staticmethod
    # async def delete_package(package_id: int):
    #     package = await Package.get_or_none(id=package_id)
    #     if package:
    #         await package.delete()
    #
    # @staticmethod
    # async def get_package_by_task_id(task_id: int) -> Package:
    #     task = await EnhanceTask.get_or_none(id=task_id)
    #     if task:
    #         return await task.package
