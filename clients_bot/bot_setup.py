import os

from aiogram import Bot, Dispatcher, Router
from dotenv import load_dotenv
from loguru import logger

load_dotenv()
bot_token = os.environ.get("CLIENTS_BOT_TOKEN")

bot = Bot(token=bot_token)
dp = Dispatcher()

command_router = Router()
form_router = Router()
text_router = Router()

sessions = {}

log_folder = os.path.join(os.getcwd(), "clients_bot/logs")
if not os.path.exists(log_folder):
    os.makedirs(log_folder)


logger.add(
    os.path.join(log_folder, "clients_bot.log"),
    format="{time} {level} {message}",
    rotation="10 MB",
    compression="zip",
    level="DEBUG"
)
