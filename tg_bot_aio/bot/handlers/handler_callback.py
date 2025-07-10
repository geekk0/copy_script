import os

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext


from ..bot_setup import logger
from ..keyboards import create_kb
from ..middleware import ChatIDChecker
from ..modes.statistics import start_stats_mode
from ..service import studio_path, studio_names, mode_names
from ..sessions import Session
from ..modes.indexing import start_index_mode
from ..modes.sharing import start_sharing_mode
from ..modes.enhance_config import start_enhance_mode
from ..modes.queues import start_queue_mode
from ..keyboards import enhance_rs_kb

callback_router = Router()


@callback_router.callback_query(F.data.in_(mode_names))
async def handle_mode_callback(callback: CallbackQuery, state: FSMContext):
    mode = callback.data

    if mode in ["Индексация", "ИИ Обработка", "Обработка:запустить"]:
        await start_index_mode(callback, state)
    elif mode == "Обработка:настройки":
        await start_enhance_mode(callback, state)
    elif mode == "Ссылка на видео":
        await start_sharing_mode(callback, state)
    elif mode == "Рассылка":
        await callback.message.edit_text(text="Управление рассылкой в данный момент не поддерживается")
    elif mode == "Очереди ФШ":
        await start_queue_mode(callback, state)
    elif mode == "Статистика":
        await start_stats_mode(callback, state)

callback_router.message.middleware(ChatIDChecker())

@callback_router.callback_query(F.data.in_(['Обработка']))
async def handle_mode_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text='Выберите режим', reply_markup=enhance_rs_kb)

callback_router.message.middleware(ChatIDChecker())
