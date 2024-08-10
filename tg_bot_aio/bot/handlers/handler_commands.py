import os

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from ..keyboards import create_kb
from ..service import studio_path, studio_names, mode_names
from ..middleware import ChatIDChecker
from ..bot_setup import logger

command_router = Router()


@command_router.message(CommandStart())
async def handle_start_command(message: Message, state: FSMContext):
    await state.clear()
    kb = await create_kb(mode_names, mode_names * len(mode_names))
    await message.answer(text="Выберите действие:", reply_markup=kb)


command_router.message.middleware(ChatIDChecker())
