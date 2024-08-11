import os
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ChatPhoto
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from ..bot_setup import logger, form_router, sessions
from ..sessions import Session
from ..keyboards import create_kb
from ..middleware import ChatIDChecker
from ..service import studio_names, mode_names
from ..utils import (run_indexing, check_ready_for_index, change_ownership,
                     get_ai_queue, add_to_ai_queue)


class IndexingForm(StatesGroup):
    studio = State()
    month = State()
    date = State()
    time = State()


async def start_index_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data
    await state.update_data(mode=mode, path='/cloud/reflect/files')
    await state.set_state(IndexingForm.studio)
    studios_kb = await create_kb(studio_names, studio_names * len(studio_names))
    await callback.message.edit_text(text=f"{mode}, выберите студию", reply_markup=studios_kb)


async def process_step(callback: CallbackQuery, state: FSMContext, next_state: State, text_template: str):
    data = await state.get_data()
    studio = data.get('studio')
    path = os.path.join(data.get('path'), callback.data)
    await state.update_data(path=path)

    folders_list = sorted([entry for entry in os.listdir(path)
                           if os.path.isdir(os.path.join(path, entry))])
    folders_kb = await create_kb(folders_list, folders_list * len(folders_list))
    await state.set_state(next_state)
    await callback.message.edit_text(text=text_template.format(studio), reply_markup=folders_kb)


@form_router.callback_query(IndexingForm.studio)
async def process_studio(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.update_data(studio=callback.data)
    await process_step(callback, state, IndexingForm.month, f"{data.get('mode')}, выберите месяц")


@form_router.callback_query(IndexingForm.month)
async def process_month(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.update_data(month=callback.data)
    await process_step(callback, state, IndexingForm.date, f"{data.get('mode')}, выберите дату")


@form_router.callback_query(IndexingForm.date)
async def process_date(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.update_data(date=callback.data)
    await process_step(callback, state, IndexingForm.time, f"{data.get('mode')}, выберите время")


@form_router.callback_query(IndexingForm.time)
async def process_time(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.update_data(time=callback.data)
    path = os.path.join(data.get('path'), callback.data)

    if data.get('mode') == 'Индексация':
        await callback.message.edit_text(text="Проверка папки, это займет до 10 секунд...")
        if await check_ready_for_index(path):
            await change_ownership(path)
            result = await run_indexing(path)
            await state.clear()
            kb = await create_kb(mode_names, mode_names * len(mode_names))
            await callback.message.edit_text(text=f"{path}: {result}", reply_markup=kb)
        else:
            await callback.message.answer(text="Файлы еще копируются")
    elif data.get('mode') == 'ИИ обработка':
        await add_to_ai_queue(path)
        await callback.message.edit_text(text=f"Папка {path} \n добавлена в очередь")

form_router.message.middleware(ChatIDChecker())
