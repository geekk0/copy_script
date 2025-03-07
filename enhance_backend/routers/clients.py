from fastapi import APIRouter, HTTPException, Response
from tortoise.exceptions import DoesNotExist

from enhance_backend.models import Client
from enhance_backend.schemas import ClientResponse, ClientRequest
from enhance_backend.db_manager import DatabaseManager

clients_router = APIRouter(prefix="/clients")

db_manager = DatabaseManager()


@clients_router.get("")
async def get_client_by_chat_id(client_chat_id: int) -> ClientResponse | None:
    try:
        client = await db_manager.get_client_by_chat_id(client_chat_id)
        return client
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@clients_router.post("")
async def add_client(client_data: ClientRequest) -> ClientResponse:
    try:
        client = await db_manager.add_client(client_data)
        return ClientResponse.model_validate(client)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@clients_router.delete("")
async def remove_client(client_chat_id: int) -> dict[str, str]:
    try:
        await db_manager.remove_client(int(client_chat_id))
        return {"message": "Client removed successfully"}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Client not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@clients_router.get("/list")
async def get_all_clients() -> list[ClientResponse]:
    try:
        clients = await Client.all()
        return clients
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@clients_router.patch("")
async def update_client(client_chat_id: int, client_data: ClientRequest) -> ClientResponse:
    try:
        client = await db_manager.get_client_by_chat_id(client_chat_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        updated_client = await db_manager.update_client(client_chat_id, client_data)
        return ClientResponse.model_validate(updated_client)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
