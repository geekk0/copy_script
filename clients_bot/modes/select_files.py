import os
import asyncio
from time import sleep

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ChatPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile
from datetime import datetime
from PIL import Image, ImageOps

from clients_bot.bot_setup import logger
from clients_bot.bot_setup import form_router
from clients_bot.keyboards import create_kb
from clients_bot.db_manager import DatabaseManager
from clients_bot.api_manager import YClientsAPIManager
from clients_bot.models import Record, EnhanceTask
from clients_bot.utils import clear_photo_folder

db_manager = DatabaseManager()
api_manager = YClientsAPIManager()


class SelectFilesForm(StatesGroup):
    create_user = State()
    get_user_records = State()
    process_selected_record = State()
    send_folder_photos = State()
    process_selected_photos = State()


async def start_select_files_form(message: Message, state: FSMContext):
    mode = "select_files"
    logger.debug(f'mode: {mode}')
    user = await db_manager.get_client_by_chat_id(message.chat.id)
    if user:
        logger.debug(f'client with id: {message.chat.id} already exists')
        if user:
            await state.update_data(client_phone=user.phone_number,
                                    yclients_user_id=user.yclients_id)
            await state.set_state(SelectFilesForm.get_user_records)
            await get_records(message, state)

    else:
        logger.debug(f'client with id: {message.chat.id} not exists')
        await message.answer(text='Введите номер телефона')
        await state.set_state(SelectFilesForm.create_user)


async def format_record_date(date) -> str:
    dt = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%d.%m.%y %H:%M")


async def get_record_folder(record: dict) -> str:
    studio_name = record.get('studio', '')
    date_str = record.get('date', '')
    try:
        date = datetime.strptime(date_str, "%d.%m.%y %H:%M")

        studios_mapping = {
            "НЕО": "Neo", "Силуэт": "Силуэт", "Портрет": "Портрет",
            "Отражение": "Отражение"
        }

        studio_name = studios_mapping[studio_name]

        month_russian = [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ]
        month = month_russian[date.month - 1]
        day = date.day
        hour = date.hour

        folder = (f"/cloud/reflect/files/{studio_name}/{month} {studio_name.upper()}/{day:02d}"
                  f".{date.month:02d}/{hour}-{hour + 1}")

        return folder
    except ValueError:
        return "Invalid date format"


async def check_record_before_create_task(record: dict, folder_path):
    result = {'status': True, 'message': None, 'exists': False}

    if not os.path.exists(folder_path):
        result = {'status': False,
                  'message': f'Папка \n"{folder_path}"\n не найдена на сервере', 'exists': False}
        return result

    existing_task = await EnhanceTask.filter(yclients_record_id=record.get('record_id')).first()
    if existing_task:
        if existing_task.enhanced_files_count < 10:
            result = {'status': True, 'message': None, 'exists': True}
        else:
            result['status'] = False
            result['message'] = f"Фото уже выбраны для этого сеанса"
    return result


async def compress_image(image_name, image_path):
    new_name = image_name.replace('.jpg', "_compressed.jpg")
    output_path = os.path.join(os.getcwd(), "photos", new_name)

    if not os.path.exists(output_path):
        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img.thumbnail((700, 700))
            img.save(output_path, "JPEG", quality=55)

    return new_name


@form_router.message(SelectFilesForm.create_user)
async def create_user(message: Message, state: FSMContext):
    phone = message.text
    user_data = await api_manager.get_client_info_by_phone(phone)
    logger.debug(f"user data: {user_data}")
    yclients_user_id = user_data.get('data')[0].get('id')
    logger.debug(f'yclients_user_id: {yclients_user_id}')
    await state.update_data(yclients_user_id=yclients_user_id)

    await db_manager.add_client(message.chat.id, phone, yclients_user_id)
    logger.debug(f'client with id: {message.chat.id} added')
    await state.set_state(SelectFilesForm.get_user_records)
    await get_records(message, state)


@form_router.message(SelectFilesForm.get_user_records)
async def get_records(message: Message, state: FSMContext):
    data = await state.get_data()
    yclients_user_id = data.get('yclients_user_id')
    result = await api_manager.get_client_records_by_client_id(yclients_user_id)
    records = []
    for record in result.get('data'):
        record_object = Record(
            record_id=record.get('id'),
            date=await format_record_date(record.get('date')),
            studio=record.get('staff').get('name').split('"')[1]
        )
        records.append(record_object)

    await state.update_data(records_objects=[record.model_dump() for record in records])

    record_ids = [str(record.record_id) for record in records]
    record_dates = [record.date for record in records]

    records_kb = await create_kb(record_dates, record_ids)
    await state.set_state(SelectFilesForm.process_selected_record)
    await message.answer(text="Выберите нужную запись", reply_markup=records_kb)


@form_router.callback_query(SelectFilesForm.process_selected_record)
async def process_selected_record(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_record_dict = [x for x in data.get('records_objects')
                            if x.get('record_id') == int(callback.data)][0]
    logger.debug(f"selected record: {selected_record_dict}")
    folder_path = await get_record_folder(selected_record_dict)
    logger.debug(f"folder_path: {folder_path}")

    checks_result = await check_record_before_create_task(selected_record_dict, folder_path)

    if checks_result.get('status'):
        if not checks_result.get('exists'):
            task = await db_manager.add_enhance_task(
                callback.message.chat.id,
                folder_path,
                int(selected_record_dict.get('record_id'))
            )
            logger.debug(f"created task: {task}")

        await state.update_data(folder_path=folder_path)
        await state.set_state(SelectFilesForm.send_folder_photos)
        await send_folders_photos(callback.message, state)
    else:
        await callback.message.edit_text(f"{checks_result.get('message')}",
                                         reply_markup=callback.message.reply_markup)


@form_router.callback_query(SelectFilesForm.send_folder_photos)
async def send_folders_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    user_selected_photos = []
    original_photo_path = data.get('folder_path')
    logger.debug(f"original_photo_path: {original_photo_path}")
    logger.debug(f"user_selected_photos: {user_selected_photos}")

    with os.scandir(original_photo_path) as files:
        for photo in files:
            try:
                if photo.is_file():
                    compressed_image = await compress_image(photo.name, photo.path)

                    logger.debug(f"compressed_image: {compressed_image}")

                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="Выбрать", callback_data=f"select:{compressed_image}")]
                        ]
                    )
                    await message.answer_photo(
                        FSInputFile(os.path.join(os.getcwd(), "photos", compressed_image)),
                        reply_markup=keyboard
                    )
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"{e}")

    done_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Готово", callback_data="done_selection")] # ✅
        ]
    )
    await state.update_data(user_selected_photos=user_selected_photos)
    await state.set_state(SelectFilesForm.process_selected_photos)
    await message.answer("Когда выберете все фото, нажмите 'Готово'.", reply_markup=done_button)


@form_router.callback_query(SelectFilesForm.process_selected_photos)
async def process_selected_photos(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_selected_photos = data.get('user_selected_photos')
    tg_photos_path = os.path.join(os.getcwd(), "clients_bot", "photos")

    logger.debug(f"user_selected_photos: {user_selected_photos}")
    logger.debug(f"callback.data: {callback.data}")

    if callback.data.startswith("select:"):
        photo_path = callback.data.split(":")[1]
        logger.debug(f"selected photo path: {photo_path}")
        if photo_path in user_selected_photos:
            user_selected_photos.remove(photo_path)
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Фото убрано из выбора ❌", callback_data=callback.data)]
                ]
            )
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.answer("Количество выбранных фото: " + str(len(user_selected_photos)))

        else:
            user_selected_photos.append(photo_path)
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Фото выбрано", callback_data=callback.data)]
                ]
            )
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.answer("Количество выбранных фото: " + str(len(user_selected_photos)))

    elif callback.data == "done_selection":
        if user_selected_photos:
            await callback.message.answer(f"Выбранные Вами фото:\n {user_selected_photos}")
            await clear_photo_folder(tg_photos_path)
        else:
            await callback.message.answer("Вы не выбрали ни одного фото.")

    await callback.answer()
