import os

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message
from aiogram.types import CallbackQuery
from datetime import datetime
from PIL import Image, ImageOps

from clients_bot.bot_setup import logger
from clients_bot.bot_setup import form_router
from clients_bot.keyboards import create_kb
from clients_bot.db_manager import DatabaseManager
from clients_bot.api_manager import YClientsAPIManager
from clients_bot.models import Record, EnhanceTask
from clients_bot.utils import prepare_enhance_task, add_to_ai_queue

db_manager = DatabaseManager()
api_manager = YClientsAPIManager()


class SelectFilesForm(StatesGroup):
    create_user = State()
    get_user_records = State()
    process_selected_record = State()
    process_digits_set = State()


studios_mapping = {
            "НЕО": "Neo", "Силуэт": "Силуэт", "Портрет": "Портрет",
            "Отражение": "Отражение"
        }


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
    original_photo_path = await get_record_folder(selected_record_dict)
    checks_result = await check_record_before_create_task(
        selected_record_dict, original_photo_path)
    await state.update_data(
        original_photo_path=original_photo_path,
        selected_record_dict=selected_record_dict,
        checks_result=checks_result,
    )
    if checks_result.get('status'):
        await state.set_state(SelectFilesForm.process_digits_set)
        if checks_result.get('exists'):
            existing_task = await EnhanceTask.get(
                yclients_record_id=int(selected_record_dict.get('record_id')))
            await callback.message.edit_text(
                f"Для этой записи выбрано {len(existing_task.files_list)} фото"
                f" Введите через пробел цифровые значения "
                f"из названий {10 - len(existing_task.files_list)} файлов")
        else:
            await callback.message.edit_text(
                "Введите через пробел цифровые значения из названий 10 файлов")
    else:
        await callback.message.edit_text(f"{checks_result.get('message')}",
                                         reply_markup=callback.message.reply_markup)


@form_router.message(SelectFilesForm.process_digits_set)
async def process_digits_set(message: Message, state: FSMContext):
    data = await state.get_data()
    original_photo_path = data.get('original_photo_path')
    checks_result = data.get('checks_result')
    selected_record_dict = data.get('selected_record_dict')

    photos_digits_set = set(message.text.split(" "))
    found_files = set()

    logger.debug(f"photos_digits_set: {photos_digits_set}")

    if len(list(message.text.split(" "))) > 10:
        await message.answer("Количество фото превышено")

    try:
        for file in os.scandir(original_photo_path):
            if file.is_file():
                try:
                    file_number_str = file.name.split('-')[1].split('.')[0]
                    if file_number_str in photos_digits_set:
                        found_files.add(file.name)
                except (IndexError, ValueError):
                    continue

        missing_numbers = (photos_digits_set -
                           {file.name.split('-')[1].split('.')[0]
                            for file in os.scandir(original_photo_path) if file.is_file()})
        logger.debug(f"missing numbers: {missing_numbers}")

        if missing_numbers:
            await message.answer(
                f"Эти номера не соответствуют "
                f"названиям Ваших фотографий: {' '.join(map(str, missing_numbers))}")
        else:
            if checks_result.get('exists'):
                existing_task = await EnhanceTask.get(
                    yclients_record_id=int(selected_record_dict.get('record_id'))
                )

                if existing_task.enhanced_files_count + len(found_files) > 10:
                    await message.answer("Общее количество выбранных фото превышено")
                else:
                    existing_task.files_list = (
                            (existing_task.files_list or []) + list(found_files))
                    await existing_task.save()
            else:
                new_task = await db_manager.add_enhance_task(
                    message.chat.id,
                    original_photo_path,
                    int(selected_record_dict.get('record_id')),
                    list(found_files)
                )
                logger.debug(f"created task: {new_task}")

            try:
                await prepare_enhance_task(original_photo_path, list(found_files))
            except Exception as e:
                logger.error(f"error prepare_enhance_task: {e}")
            try:
                await add_to_ai_queue(
                    original_photo_path + "_demo",
                    studios_mapping[selected_record_dict.get('studio')],
                    True
                )
            except Exception as e:
                logger.error(f"error add_to_ai_queue: {e}")
            await message.answer(f"Файлы для обработки:\n"
                                 f"{' '.join(map(str, found_files))}")

    except Exception as e:
        logger.error(f"{e}")




