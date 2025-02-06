import os
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ChatPhoto
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from ..bot_setup import form_router, logger
from ..keyboards import create_kb
from ..middleware import ChatIDChecker
from ..service import studio_names, mode_names
from ..utils import (run_indexing, check_ready_for_index,
                     change_ownership, change_folder_permissions,
                     add_to_ai_queue, run_rs_enhance)


class QueueForm(StatesGroup):
    queue_number = State()
    queue_list = State()


queues_mapping = {
    'queue_1': "Очередь 1",
    'queue_list': "Очередь 2",
}


async def start_queue_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data
    logger.info(f'mode: {mode}')
    await state.update_data(mode=mode)
    await state.set_state(QueueForm.queue_number)
    queues_kb = await create_kb(list(queues_mapping.keys()), list(queues_mapping.values()) * 2)
    await callback.message.edit_text(text=f"{mode}, выберите очередь", reply_markup=queues_kb)

form_router.message.middleware(ChatIDChecker())
