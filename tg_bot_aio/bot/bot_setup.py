import os
import asyncio

from aiogram import Bot, Dispatcher, Router
from dotenv import load_dotenv
from loguru import logger

load_dotenv()
bot_token = os.environ.get("BOT_TOKEN")

bot = Bot(token=bot_token)
dp = Dispatcher()

command_router = Router()
form_router = Router()
text_router = Router()

sessions = {}

logger.add("tg_bot.log",
           format="{time} {level} {message}",
           rotation="10 MB",
           compression='zip',
           level="INFO")

log_folder = "logs"
if not os.path.exists(log_folder):
    os.makedirs(log_folder)

logger.add(
    os.path.join(log_folder, "tg_bot.log"),
    format="{time} {level} {message}",
    rotation="10 MB",
    compression="zip",
    level="INFO"
)

