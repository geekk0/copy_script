import os
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ChatPhoto
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from clients_bot.enhance_backend_api import EnhanceBackendAPI
from ..bot_setup import form_router, logger
from ..keyboards import create_kb
from ..middleware import ChatIDChecker
from ..service import studio_names, mode_names
from ..utils import (run_indexing, check_ready_for_index,
                     change_ownership, change_folder_permissions,
                     add_to_ai_queue, run_rs_enhance, get_readable_queue, count_files_in_folder, remove_from_ai_queue,
                     ai_caller_restart)


class QueueForm(StatesGroup):
    queues_select = State()
    queue_schedule = State()
    folder_details = State()
    process_folder_screen = State()


queues_mapping = {
    "Очередь 1": "ai_enhance_queue_ph_1.json",
    "Очередь 2": "ai_enhance_queue_ph_2.json"
}


async def start_queue_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data
    logger.info(f'mode: {mode}')
    await state.update_data(mode=mode)
    await state.set_state(QueueForm.queues_select)
    await callback.message.edit_text(text=f"Введите пароль")
    await state.update_data(message_to_delete_id=callback.message.message_id)


@form_router.message(QueueForm.queues_select)
async def queues_select_screen(message: Message, state: FSMContext):
    try:
        password_match = False
        data = await state.get_data()
        logged_in = data.get('logged_in')
        await state.update_data(selected_queue=None)
        if not logged_in:
            message_id = data.get('message_to_delete_id')
            await message.bot.delete_message(message.chat.id, message_id)
            await message.delete()
            password = message.text
            password_match = password == '123456Qe'

        if password_match or logged_in:
            await state.update_data(logged_in=True)
            await state.set_state(QueueForm.queue_schedule)
            final_kb_keys = list(queues_mapping.keys()) + ["Рестарт сервиса", "Логаут клиента"]
            final_kb_values = list(queues_mapping.values()) + ["service_restart", "logout"]
            queues_kb = await create_kb(final_kb_keys, final_kb_values)

            await message.answer(text=f"выберите очередь", reply_markup=queues_kb)
        else:
            await message.answer("Неправильный пароль", protect_content=True)
    except Exception as e:
        logger.error(e)


@form_router.callback_query(QueueForm.queue_schedule)
async def process_queue_select(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_queue = data.get('selected_queue')
    queue_name = data.get('queue_name')

    if callback.data == "service_restart":
        result = await ai_caller_restart()
        await callback.message.edit_text(f"Результат: {result}",
                                         reply_markup=callback.message.reply_markup)

    elif callback.data == "logout":
        await callback.message.edit_text(f"Введите номер телефона клиента")

    if not selected_queue:
        selected_queue = callback.data
        queue_name = [key for key, val
                      in queues_mapping.items() if val == callback.data][0]

        await state.update_data(selected_queue=callback.data, queue_name=queue_name)

    readable_queue_list = await get_readable_queue(selected_queue)
    logger.info(f"readable_queue_list: {readable_queue_list}")
    await state.update_data(readable_queue_list=readable_queue_list)
    await state.set_state(QueueForm.folder_details)

    if readable_queue_list:

        folders_buttons = [x.get('folder_path').replace('/cloud/reflect/files/', '') for x in readable_queue_list]

        folders_mapping = {}
        for i in range(0, len(readable_queue_list)):
            folder_path = readable_queue_list[i].get('folder_path')
            folders_mapping[str(i)] = {
                'path': folder_path,
                'action': readable_queue_list[i].get('action'),
                'files': str(await count_files_in_folder(folder_path))
            }

        await state.update_data(folders_mapping=folders_mapping)

        try:
            logger.info("before append")
            folders_kb = await create_kb(
                list(folders_buttons) + ["Назад"],
                list(folders_mapping.keys()) + ["Назад"])
            await callback.message.edit_text(f'{queue_name}, выберите папку: ', reply_markup=folders_kb)
            logger.info("after append")

        except Exception as e:
            logger.error(e)
    else:
        delete_kb = await create_kb(['Назад'], ['Назад'])
        await callback.message.edit_text(
            f'Очередь "{queue_name}" пуста', reply_markup=delete_kb)


@form_router.callback_query(QueueForm.folder_details)
async def folder_details_screen(callback: CallbackQuery, state: FSMContext):
    logger.info(f"callback_data: {callback.data}")
    if callback.data == "Назад":
        await queues_select_screen(callback.message, state)
        # await state.set_state(QueueForm.queues_select)
    else:
        try:
            folders_mapping = (await state.get_data()).get("folders_mapping")
            selected_folder = folders_mapping[callback.data].get('path')
            selected_folder_action = folders_mapping[callback.data].get('action')
            selected_folder_files = folders_mapping[callback.data].get('files')
            await state.update_data(
                selected_folder=selected_folder,
                selected_folder_action=selected_folder_action,
            )
            if not selected_folder_action:
                selected_folder_action = "из конфига студии"
            readable_queue_list = (await state.get_data()).get("readable_queue_list")
            logger.info(f"readable_queue_list: {readable_queue_list}")

            await state.set_state(QueueForm.process_folder_screen)

            kb = await create_kb(['Назад', 'Удалить'], ['Назад', 'Удалить'])
            await callback.message.edit_text(
                f"Папка: {selected_folder.replace('/cloud/reflect/files/', '')} "
                f"\nЭкшн: {selected_folder_action} "
                f"\nФайлов: {selected_folder_files}", reply_markup=kb)

        except Exception as e:
            logger.error(e)


@form_router.callback_query(QueueForm.folder_details)
async def process_logout(message: Message, state: FSMContext):
    data = await state.get_data()
    phone_number = message.text
    if phone_number:
        enhance_backend_api = EnhanceBackendAPI()
        response = await enhance_backend_api.remove_client(client_phone=phone_number)
        if response.status_code == 200:
            await message.answer(text="Учетная запись клиента удалена")
        else:
            await message.answer(text="Не получилось удалить учетку клиента")



@form_router.callback_query(QueueForm.process_folder_screen)
async def process_details_screen(callback: CallbackQuery, state: FSMContext):
    logger.info(f"callback_data: {callback.data}")
    try:
        data = await state.get_data()
        selected_folder = data.get('selected_folder')
        selected_folder_action = data.get('selected_folder_action')
        selected_queue = data.get('selected_queue')
        if callback.data == "Назад":
            await process_queue_select(callback, state)
        elif callback.data == "Удалить":
            await remove_from_ai_queue(
                selected_folder, selected_folder_action, selected_queue)
            await process_queue_select(callback, state)
    except Exception as e:
        logger.error(e)


form_router.message.middleware(ChatIDChecker())
