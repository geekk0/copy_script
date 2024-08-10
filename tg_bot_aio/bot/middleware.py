import os
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from dotenv import load_dotenv


load_dotenv()
reflect_group_chat_id = int(os.environ.get("REFLECT_GROUP_CHAT_ID"))

class ChatIDChecker(BaseMiddleware):
    async def __call__(self, handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]], event: TelegramObject,
                       data: Dict[str, Any]) -> Any:
        if isinstance(event, Message):
            if not await self.on_pre_process_update(event):
                return
        return await handler(event, data)

    async def on_pre_process_update(self, message: Message) -> bool:
        chat_id = message.chat.id
        if chat_id in [reflect_group_chat_id]:
            return True  # Allow handler execution
        else:
            await message.reply("Доступ только из группы")
            return False  # Prevent handler execution
