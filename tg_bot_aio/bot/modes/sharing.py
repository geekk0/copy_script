import os
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ChatPhoto
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from ..middleware import ChatIDChecker
from ..bot_setup import form_router, logger
from ..bot_setup import logger, form_router, sessions, bot
from ..utils import share_video


class SharingForm(StatesGroup):
    send_share_link = State()


async def start_sharing_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data
    await state.update_data(mode=mode)
    await state.set_state(SharingForm.send_share_link)
    await callback.message.edit_text(text=f"{mode}, введите название видео с расширением")


@form_router.message(SharingForm.send_share_link)
async def get_video_name(message: Message, state: FSMContext):
    name = message.text
    result = await share_video(name)
    if result:
        await message.answer(f'[{result}]({result})', parse_mode='Markdown')

    else:
        await message.answer(text="Проверьте наличие этого видео в папке")

form_router.message.middleware(ChatIDChecker())
