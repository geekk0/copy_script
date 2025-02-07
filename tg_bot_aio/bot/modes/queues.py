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
                     add_to_ai_queue, run_rs_enhance, get_readable_queue)


class QueueForm(StatesGroup):
    queue_number = State()
    queue_list = State()


queues_mapping = {
    "Очередь 1": "ai_enhance_queue_ph_1.json",
    "Очередь 2": "ai_enhance_queue_ph_2.json"
}


async def start_queue_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data
    logger.info(f'mode: {mode}')
    await state.update_data(mode=mode)
    await state.set_state(QueueForm.queue_number)
    queues_kb = await create_kb(list(queues_mapping.keys()),
                                list(queues_mapping.values()) *
                                len(list(queues_mapping.keys())))
    await callback.message.edit_text(text=f"{mode}, "
                                          f"выберите очередь", reply_markup=queues_kb)


@form_router.callback_query(QueueForm.queue_number)
async def process_queue_select(callback: CallbackQuery, state: FSMContext):
    logger.info("process_queue_select")

    queue_name = [key for key, val
                  in queues_mapping.items() if val == callback.data][0]

    await state.update_data(selected_queue=callback.data, queue_name=queue_name)

    logger.info(callback.data)

    readable_queue_list = await get_readable_queue(callback.data)

    logger.info(f"readable_queue_list: {str(readable_queue_list)}")

    text = ""
    for element in readable_queue_list:
        text += f"\n {element.get('folder_path').replace('/cloud/reflect/files/', '')}"
        action = element.get('action')
        if action:
            text += f"\n экшн: {action}"

    if not text:
        text = f'Очередь "{queue_name}" пуста'

    await callback.message.edit_text(text)


form_router.message.middleware(ChatIDChecker())
