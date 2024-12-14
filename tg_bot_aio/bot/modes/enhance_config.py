import os
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..bot_setup import logger, form_router, sessions, bot
from ..sessions import Session
from ..keyboards import create_kb
from ..middleware import ChatIDChecker
from ..service import studio_names, mode_names
from ..utils import (run_indexing, check_ready_for_index, read_settings_file,
                     get_studio_config_file, validation_settings_value, write_settings_file)


class ImageSettings(StatesGroup):
    studio = State()
    show_parameter = State()
    process_parameter = State()
    set_parameter = State()


async def start_enhance_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data
    await state.update_data(mode=mode)
    await state.set_state(ImageSettings.studio)
    studios_kb = await create_kb(studio_names, studio_names * len(studio_names))
    await callback.message.edit_text(
        text=f"Настройка обработки, выберите студию", reply_markup=studios_kb)


@form_router.callback_query(ImageSettings.studio)
async def process_studio(callback: CallbackQuery, state: FSMContext, text=None):
    data = await state.get_data()
    studio = data.get('studio') or callback.data
    await state.update_data(studio=studio, initial_callback=callback)

    config_file_path = await get_studio_config_file(studio)
    if os.path.exists(config_file_path):

        settings = await read_settings_file(config_file_path)

        section = settings.get('image_settings')
        await state.update_data(config_file=config_file_path, image_section=section)

        section_settings_keys = []
        section_settings_items = []
        if section:
            for key in section:
                section_settings_keys.append(key)
                section_settings_items.append(f"{key}: {section[key]}")
            keyboard = await create_kb(section_settings_keys, section_settings_items)
            await state.set_state(ImageSettings.show_parameter)

            if text:
                await callback.message.answer(
                    text=text,
                    reply_markup=keyboard)
                initial_callback = data.get('initial_callback')
                await initial_callback.message.delete()
            else:

                await callback.message.edit_text(
                    text=f"Настройка обработки, выберите параметр для студии ", reply_markup=keyboard)

        else:
            await callback.message.edit_text(
                text=f'Настройки обработки для студии "{studio}" отсутствуют')
    else:
        await callback.message.answer(text=f'Не найден файл конфигурации для студии "{callback.data}"')


@form_router.callback_query(ImageSettings.show_parameter)
async def show_parameter(callback: CallbackQuery, state: FSMContext):
    parameter = callback.data.split(': ')[0]
    value = callback.data.split(': ')[1]
    actions_kb = await create_kb(['Назад'], ['Назад'])

    await state.update_data(current_parameter=parameter, current_value=value, initial_callback=callback)

    await state.set_state(ImageSettings.process_parameter)

    await callback.message.edit_text(
        text=f'{parameter}: {value}.\n Чтобы задать новое значение отправьте его сообщением',
        reply_markup=actions_kb)


@form_router.callback_query(ImageSettings.process_parameter)
async def process_parameter(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if callback.data == 'Назад':
        await state.set_state(ImageSettings.studio)
        await process_studio(callback, state)


@form_router.message(ImageSettings.process_parameter)
async def handle_parameter_input(message: Message, state: FSMContext):
    data = await state.get_data()
    parameter = data.get('current_parameter')
    old_value = data.get('current_value')

    result = await validation_settings_value(
        parameter,
        old_value,
        message.text)

    if isinstance(result, str):
        text = result
    else:
        settings_file = data.get('config_file')
        await write_settings_file(settings_file, parameter, message.text)
        text = f'Значение "{parameter}" установлено: {message.text}'

    await state.set_state(ImageSettings.show_parameter)

    mock_callback = CallbackQuery(
        id="mock_id",
        message=message,
        from_user=message.from_user,
        chat_instance=str(message.chat.id)
    )
    await process_studio(mock_callback, state, text=text)
    await message.delete()

form_router.message.middleware(ChatIDChecker())
