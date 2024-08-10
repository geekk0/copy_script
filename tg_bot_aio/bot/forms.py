# import os
# from aiogram import Router, F
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import StatesGroup, State
# from aiogram.types import Message, ChatPhoto
# from aiogram.filters import Command
# from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
#
# from .bot_setup import logger, form_router, sessions
# from .sessions import Session
# from .keyboards import create_kb
# from .middleware import ChatIDChecker
# from .service import studio_names, mode_names
# from .utils import run_indexing, check_ready_for_index
#
#
# class IndexingForm(StatesGroup):
#     studio = State()
#     month = State()
#     date = State()
#     time = State()
#
#
# @form_router.callback_query(F.data.in_(mode_names))
# async def set_mode(callback: CallbackQuery, state: FSMContext):
#     mode = callback.data
#     print(f'run set mode {mode}')
#     session = Session(mode)
#     sessions[callback.message.message_id] = session
#     await state.set_state(IndexingForm.studio)
#     studios_kb = await create_kb(studio_names, studio_names * len(studio_names))
#     await callback.message.edit_text(text=f"Индексация, выберите студию", reply_markup=studios_kb)
#
#
# async def process_step(callback: CallbackQuery, state: FSMContext, next_state: State, text_template: str):
#     session = sessions[callback.message.message_id]
#     session.path = os.path.join(session.path, callback.data)
#     folders_list = [entry for entry in os.listdir(session.path) if os.path.isdir(os.path.join(session.path, entry))]
#     folders_kb = await create_kb(folders_list, folders_list * len(folders_list))
#     await state.set_state(next_state)
#     await callback.message.edit_text(text=text_template.format(session.studio), reply_markup=folders_kb)
#
#
# @form_router.callback_query(IndexingForm.studio)
# async def process_studio(callback: CallbackQuery, state: FSMContext):
#     sessions[callback.message.message_id].studio = callback.data
#     await process_step(callback, state, IndexingForm.month, "Индексация {}, выберите месяц")
#
#
# @form_router.callback_query(IndexingForm.month)
# async def process_month(callback: CallbackQuery, state: FSMContext):
#     sessions[callback.message.message_id].month = callback.data
#     await process_step(callback, state, IndexingForm.date, "Индексация {}, выберите дату")
#
#
# @form_router.callback_query(IndexingForm.date)
# async def process_date(callback: CallbackQuery, state: FSMContext):
#     sessions[callback.message.message_id].date = callback.data
#     await process_step(callback, state, IndexingForm.time, "Индексация {}, выберите время")
#
#
# @form_router.callback_query(IndexingForm.time)
# async def process_time(callback: CallbackQuery, state: FSMContext):
#     await callback.message.edit_text(text="Проверка папки, это займет 5 секунд")
#     sessions[callback.message.message_id].time = callback.data
#     session_path = os.path.join(sessions[callback.message.message_id].path, callback.data)
#     if await check_ready_for_index(session_path):
#         result = await run_indexing(session_path)
#         await state.clear()
#         await process_step(callback, state, IndexingForm.time, f"{session_path}: {result}")
#     else:
#         await callback.message.answer(text="Файлы еще копируются")
#
#
# form_router.message.middleware(ChatIDChecker())
