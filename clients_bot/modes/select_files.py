import json
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
from clients_bot.api_manager import YClientsAPIManager
from clients_bot.utils import prepare_enhance_task, add_to_ai_queue, remove_task_folder
from clients_bot.enhance_backend_api import EnhanceBackendAPI

api_manager = YClientsAPIManager()
enh_back_api = EnhanceBackendAPI()


class SelectFilesForm(StatesGroup):
    create_user = State()
    get_user_records = State()
    show_user_tasks = State()
    process_selected_task = State()
    add_photos = State()
    process_digits_set = State()


studios_mapping = {
    "НЕО": "Neo", "Силуэт": "Силуэт", "Портрет": "Портрет",
    "Отражение": "Отражение"
}


async def start_select_files_form(message: Message, state: FSMContext):
    mode = "select_files"
    chat_id = int(message.chat.id)
    logger.debug(f'mode: {mode}')
    user = await enh_back_api.get_user_by_chat_id(chat_id)
    logger.debug(f'user: {user}')
    if user:
        await state.update_data(
            client_id=user.get("id"),
            client_phone=user.get("phone_number"),
            yclients_user_id=user.get("yclients_id")
        )
        await state.set_state(SelectFilesForm.get_user_records)
        records = await get_records(message, state)
        logger.debug(f'records: {records}')
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


async def check_record_before_create_task(record: dict, folder_path, client_id):
    result = {'status': True, 'message': None, 'exists': False}

    # if not os.path.exists(folder_path):
    #     result = {'status': False,
    #               'message': f'Папка \n"{folder_path}"\n не найдена на сервере', 'exists': False}
    #     return result

    existing_tasks = await enh_back_api.get_client_tasks(client_id)

    logger.debug(f"existing_tasks: {existing_tasks}")

    existing_session_tasks = [task for task in existing_tasks
                              if task.get('yclients_record_id')
                              == record.get('record_id')]
    if len(existing_session_tasks) > 0:
        existing_task = existing_session_tasks[0]
        package = await enh_back_api.get_package_by_task_id(existing_task.get('id'))
        logger.debug(f"existing task response: {existing_task}")
        if (existing_task.get('enhanced_files_count') +
                len(existing_task.get('files_list')) < package.get('photos_number')):
            result = {
                'status': True, 'message': None,
                'exists': True, 'task': existing_task
            }
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
    if len(user_data.get('data')) > 0:
        if user_data.get('data')[0].get('id'):
            yclients_user_id = user_data.get('data')[0].get('id')
            logger.debug(f'yclients_user_id: {yclients_user_id}')
            await state.update_data(yclients_user_id=yclients_user_id)

            new_client = await enh_back_api.add_client(
                {
                    "phone_number": phone,
                    "yclients_id": yclients_user_id,
                    "chat_id": message.chat.id
                }
            )
            logger.debug(f'client with id: {message.chat.id} added')
            await state.update_data(client_id=new_client.get('id'))
            await state.set_state(SelectFilesForm.get_user_records)
            await get_records(message, state)


@form_router.message(SelectFilesForm.get_user_records)
async def get_records(message: Message, state: FSMContext):
    data = await state.get_data()
    yclients_user_id = data.get('yclients_user_id')
    result = await api_manager.get_client_records_by_client_id(yclients_user_id)
    records = []
    for record in result.get('data'):
        record_dict = {
            'record_id': record.get('id'),
            'date': await format_record_date(record.get('date')),
            'studio': record.get('staff').get('name').split('"')[1]
        }
        records.append(record_dict)

    await state.update_data(records_objects=records)

    record_ids = [str(record.get("record_id")) for record in records]
    record_dates = [record.get("date") for record in records]

    records_kb = await create_kb(record_dates, record_ids)
    await state.set_state(SelectFilesForm.show_user_tasks)
    await message.answer(text="Выберите нужную запись", reply_markup=records_kb)


@form_router.callback_query(SelectFilesForm.show_user_tasks)
async def show_user_tasks(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    client_id = data.get('client_id')
    logger.debug(f"show_user_tasks")
    logger.debug(f"callback data: {callback.data}")
    if callback.data == "go_back":
        # await callback.message.delete()
        selected_record_dict = data.get('selected_record_dict')
    else:
        selected_record_dict = [x for x in data.get('records_objects')
                                if x.get('record_id') == int(callback.data)][0]
    logger.debug(f"selected record: {selected_record_dict}")
    existing_user_tasks = await enh_back_api.get_client_tasks(client_id)
    tasks_for_current_record = [
        task for task in existing_user_tasks
        if task.get("yclients_record_id") == selected_record_dict.get("record_id")]
    logger.debug(f"existing_user_tasks: {existing_user_tasks}")
    logger.debug(f"tasks_for_current_record: {tasks_for_current_record}")
    btn_names = [(f"Пакет: {task.get('package').get('name')},\n"
                  f"Выбрано: {len(task.get('files_list'))}")
                 for task in tasks_for_current_record]
    btn_names.append("Новый пакет")
    btn_values = [str(task.get('id')) for task in tasks_for_current_record]
    btn_values.append("new_package")
    select_package_kb = await create_kb(btn_names, btn_values)
    await state.update_data(tasks_list=tasks_for_current_record,
                            selected_record_dict=selected_record_dict)
    await callback.message.edit_text(
        text="Ваши пакеты для выбранной записи:", reply_markup=select_package_kb)
    await state.set_state(SelectFilesForm.process_selected_task)


@form_router.callback_query(SelectFilesForm.process_selected_task)
async def process_selected_task(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    logger.debug("process_selected_task")
    logger.debug(f"callback.data: {callback.data}")
    tasks_list = data.get("tasks_list")
    client_id = data.get('client_id')
    selected_record_dict = data.get("selected_record_dict")
    selected_task_dict = None
    as_new_package = data.get("as_new_package")
    await state.update_data(as_new_package=False)
    if "go_back" in callback.data:
        selected_task_dict = data.get('selected_task_dict')

    if callback.data == "new_package" or as_new_package:
        original_photo_path = await get_record_folder(selected_record_dict)
        checks_result = await check_record_before_create_task(
            selected_record_dict, original_photo_path, client_id)
        await state.update_data(
            original_photo_path=original_photo_path,
            checks_result=checks_result,
        )
        available_packages = await enh_back_api.get_available_packages()
        logger.debug(f"available_packages: {available_packages}")
        text = f"Выберите пакет"

        packages_labels = [f"{package.get('name')} - {str(package.get('price'))} руб"
                           for package in available_packages]
        packages_callbacks = [str(i) for i in range(len(available_packages))]
        packages_labels.append("Назад")
        packages_callbacks.append("go_back")
        await state.update_data(available_packages=available_packages)
        packages_kb = await create_kb(packages_labels, packages_callbacks)
        await state.set_state(SelectFilesForm.add_photos)
        await callback.message.edit_text(text=text, reply_markup=packages_kb)
    else:
        if not selected_task_dict:
            selected_task_dict = [x for x in tasks_list if x.get('id') == int(callback.data)][0]
        text = (
            f"Статус: {selected_task_dict.get('status')} \n"
            f"Выбранные файлы: "
            f"{str(selected_task_dict.get('files_list')).replace('[]', ' Нет')}"
        )
        callback_labels = ["Назад"]
        callback_data = ["go_back"]
        await state.update_data(selected_task_dict=selected_task_dict)
        if (selected_task_dict.get('package').get('photos_number')
                > len(selected_task_dict.get('files_list'))):
            callback_labels.append("Добавить фото")
            callback_data.append("add_photo")
        kb = await create_kb(callback_labels, callback_data)
        await state.set_state(SelectFilesForm.add_photos)
        await callback.message.edit_text(text=text, reply_markup=kb)


@form_router.callback_query(SelectFilesForm.add_photos)
async def add_photos(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    checks_result = data.get('checks_result')
    selected_task_dict = data.get('selected_task_dict')
    if callback.data == "go_back":
        await state.update_data(selected_task_dict=None, selected_package=None)
        await state.set_state(SelectFilesForm.show_user_tasks)
        await show_user_tasks(callback, state)
        return
    if not selected_task_dict:
        selected_package = data.get('available_packages')[int(callback.data)]
        await state.update_data(
            selected_package=selected_package)
        if checks_result.get('status'):
            await state.set_state(SelectFilesForm.process_digits_set)
            kb = await create_kb(["Назад"], ["go_back:new_package"])
            await callback.message.edit_text(
                f"Выберите фото для обработки из Вашей папки\n"
                f"введите через пробел цифровые значения "
                f"из названий до {selected_package.get(
                    'photos_number')} файлов",
                reply_markup=kb
            )
        else:
            await state.update_data(selected_task_dict=None, selected_package=None)
            logger.warning(f"checks_result message: {checks_result.get('message')}")
            await callback.message.edit_text(f"Не удалось создать задачу по обработке",
                                             reply_markup=callback.message.reply_markup)
    else:
        await state.set_state(SelectFilesForm.process_digits_set)
        kb = await create_kb(["Назад"], ["go_back:package_selected"])
        await callback.message.edit_text(
            f"Для Вашей папки выбрано "
            f"{len(selected_task_dict.get('files_list'))} фото"
            f" Введите через пробел цифровые значения "
            f"из названий до {selected_task_dict.get('package').get('photos_number') - 
                              len(selected_task_dict.get('files_list'))} файлов",
            reply_markup=kb)


@form_router.message(SelectFilesForm.process_digits_set)
async def process_digits_set(message: Message, state: FSMContext):
    data = await state.get_data()
    original_photo_path = data.get('original_photo_path')
    checks_result = data.get('checks_result')
    selected_record_dict = data.get('selected_record_dict')
    selected_package = data.get('selected_package')

    photos_digits_set = set(message.text.split(" "))
    found_files = set()

    logger.debug(f"photos_digits_set: {photos_digits_set}")

    if len(list(message.text.split(" "))) > selected_package.get('photos_number'):
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
                existing_task = checks_result.get('task')

                if (existing_task.get('enhanced_files_count') +
                        len(found_files) > selected_package.get('photos_number')):
                    await message.answer("Общее количество выбранных фото превышено")
                else:
                    existing_task['files_list'] = (
                            (existing_task.get('files_list') or []) + list(found_files))
                    await enh_back_api.update_enhance_task(
                        task_id=existing_task.get('id'),
                        task_data={
                            'files_list': existing_task.get('files_list'),
                            'status': "processing"
                        }
                    )
            else:
                new_task = await enh_back_api.add_enhance_task(
                    task_data={
                        'folder_path': original_photo_path,
                        'yclients_record_id': int(selected_record_dict.get('record_id')),
                        'files_list': list(found_files),
                        "client_chat_id": message.chat.id,
                        'package_id': data.get('selected_package').get('id')
                    }
                )
                logger.debug(f"created task: {new_task}")

            try:
                await prepare_enhance_task(original_photo_path, list(found_files))
            except Exception as e:
                logger.error(f"error prepare_enhance_task: {e}")
            try:
                await add_to_ai_queue(
                    original_photo_path + "_task",
                    studios_mapping[selected_record_dict.get('studio')],
                    True
                )
                await enh_back_api.change_task_status(original_photo_path, "queued")
            except Exception as e:
                logger.error(f"error add_to_ai_queue: {e}")

            await message.answer(
                f"Выбраны для обработки:\n"
                f"{' '.join(map(str, found_files))}\n"
                f"Фото добавлены в очередь, мы сообщим Вам как только они обработаются"
            )

    except Exception as e:
        logger.error(f"{e}")


@form_router.callback_query(SelectFilesForm.process_digits_set)
async def process_digits_set_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_task_dict = data.get('selected_task_dict')
    logger.debug(f"process_digits_set_callback")
    logger.debug(f"selected_task_dict: {selected_task_dict}")
    if "go_back" in callback.data:
        if "new_package" in callback.data:
            await state.update_data(as_new_package=True)
        await state.update_data(selected_package=None)
        await state.set_state(SelectFilesForm.process_selected_task)
        await process_selected_task(callback, state)
        return
