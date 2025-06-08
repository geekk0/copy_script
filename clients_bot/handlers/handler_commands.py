import os
import sys

# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

# from clients_bot.middleware import ChatIDChecker
# from clients_bot.bot_setup import logger
from ..middleware import ChatIDChecker
from ..bot_setup import logger
from ..modes.select_files import start_select_files_form, enh_back_api

command_router = Router()


@command_router.message(CommandStart())
async def handle_start_command(message: Message, state: FSMContext):
    await start_select_files_form(message, state)


# @command_router.message(Command("choose_photos"))
# async def choose_photos(message: Message, state: FSMContext):
#     await start_select_files_form(message, state)


# @command_router.message(Command("logout"))
# async def logout(message: Message):
#     await enh_back_api.remove_client(message.from_user.id)


# command_router.message.middleware(ChatIDChecker())
