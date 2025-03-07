from os import environ

from aiogram import Bot
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()


class ClientsBot:
    BOT_TOKEN = environ.get('CLIENTS_BOT_TOKEN')
    bot = Bot(token=BOT_TOKEN)

    async def send_notification(self, chat_id: int, text: str):
        await self.bot.send_message(chat_id=chat_id, text=text)

