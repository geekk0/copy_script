import json
import os

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import CallbackQuery
from datetime import datetime
from PIL import Image, ImageOps
from dotenv import load_dotenv

from clients_bot.bot_setup import logger, bot
from clients_bot.bot_setup import form_router
from clients_bot.keyboards import create_kb
from clients_bot.api_manager import YClientsAPIManager
from clients_bot.utils import prepare_enhance_task, add_to_ai_queue, remove_task_folder
from clients_bot.enhance_backend_api import EnhanceBackendAPI


load_dotenv()
YOOKASSA_PROVIDER_TOKEN = os.getenv("YOOKASSA_PROVIDER_TOKEN")

api_manager = YClientsAPIManager()
enh_back_api = EnhanceBackendAPI()


class SelectFilesForm(StatesGroup):
    create_user = State()
    get_user_records = State()
    show_user_certs = State()
    show_user_tasks = State()
    process_certs_screen = State()
    show_selected_task = State()
    process_selected_task = State()
    new_task_screen = State()
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

    existing_tasks = await enh_back_api.get_client_tasks(client_id, record.get('record_id'))

    logger.debug(f"existing_tasks: {existing_tasks}")

    existing_session_tasks = [task for task in existing_tasks
                              if task.get('yclients_record_id')
                              == record.get('record_id')]
    if len(existing_session_tasks) > 0:
        existing_task = existing_session_tasks[0]
        package = await enh_back_api.get_package_by_task_id(existing_task.get('id'))
        logger.debug(f"existing task response: {existing_task}")
        if (existing_task.get('enhanced_files_count') +
                len(existing_task.get('files_list')) < existing_task.get('max_photo_amount')):
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
    await state.set_state(SelectFilesForm.show_user_certs)
    await message.answer(text="Выберите нужную запись", reply_markup=records_kb)


@form_router.callback_query(SelectFilesForm.show_user_certs)
async def show_user_certs(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    client_id = data.get('client_id')
    logger.debug("show_user_certs")
    logger.debug(f"callback data: {callback.data}")
    if "go_back" in callback.data:
        selected_record_dict = data.get('selected_record_dict')
    else:
        selected_record_dict = [x for x in data.get('records_objects')
                                if x.get('record_id') == int(callback.data)][0]
    logger.debug(f"selected record: {selected_record_dict}")
    existing_user_tasks = await enh_back_api.get_client_tasks(
        client_id, selected_record_dict.get("record_id"))
    tasks_for_current_record = [
        task for task in existing_user_tasks
        if task.get("yclients_record_id") == selected_record_dict.get("record_id")]
    logger.debug(f"existing_user_tasks: {existing_user_tasks}")
    logger.debug(f"tasks_for_current_record: {tasks_for_current_record}")

    user = await enh_back_api.get_user_by_chat_id(callback.message.chat.id)
    all_certs = (await api_manager.get_enhance_certs(user.get('phone_number'))).get('data')
    logger.debug(f"all_certs: {all_certs}")

    btn_names = []
    btn_values = []

    if existing_user_tasks:
        existing_cert_numbers = [str(task["yclients_certificate_code"])
                                 for task in existing_user_tasks]
        free_certs = [cert for cert in all_certs
                      if cert.get('number') not in existing_cert_numbers]
    else:
        free_certs = all_certs

    if free_certs:
        btn_names += [f"{p.get('type').get('title').replace('Обработка ', '')}"
                      for p in free_certs]
        btn_values += [str(i) for i in range(0, len(free_certs))]
        await state.update_data(free_certs=free_certs)

    btn_names.append("Новый пакет")
    btn_values.append("new_package")

    if existing_user_tasks:
        btn_names.append("В обработке")
        btn_values.append("existing_tasks")
        await state.update_data(existing_user_tasks=existing_user_tasks)

    btn_names.append("Назад")
    btn_values.append("go_back")

    select_package_kb = await create_kb(btn_names, btn_values)

    await state.update_data(
        tasks_list=tasks_for_current_record,
        selected_record_dict=selected_record_dict,
    )
    await state.set_state(SelectFilesForm.process_certs_screen)
    await callback.message.edit_text(
        text="Выберите имеющийся или новый пакет:", reply_markup=select_package_kb)


@form_router.callback_query(SelectFilesForm.process_certs_screen)
async def process_certs_screen(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_task_dict = data.get('selected_task_dict')
    logger.debug("process_certs_screen")
    logger.debug(f"callback.data: {callback.data}")
    logger.debug(f"selected_task_dict: {selected_task_dict}")
    tasks_list = data.get("existing_user_tasks")
    client_id = data.get('client_id')
    selected_record_dict = data.get("selected_record_dict")
    free_certs = data.get("free_certs")
    as_new_package = data.get("as_new_package")
    await state.update_data(as_new_package=False)
    if "go_back" in callback.data:
        await state.set_state(SelectFilesForm.show_user_certs)
        await show_user_certs(callback, state)
        return

    elif callback.data == "new_package" or as_new_package:
        available_packages = await enh_back_api.get_available_packages()
        logger.debug(f"available_packages: {available_packages}")
        text = f"Выбор и оплата пакета"

        packages_labels = [f"{package.get('name')} - {str(package.get('price'))} руб"
                           for package in available_packages]
        packages_callbacks = [p.get('purchase_url') for p in available_packages]
        packages_labels.append("Назад")
        packages_callbacks.append("go_back")
        await state.update_data(available_packages=available_packages)
        packages_kb = await create_kb(packages_labels, packages_callbacks)

        await state.set_state(SelectFilesForm.new_task_screen)
        await callback.message.edit_text(text=text, reply_markup=packages_kb)
        return
    elif callback.data == "existing_tasks":
        await state.set_state(SelectFilesForm.show_user_tasks)
        await show_user_tasks(callback, state)
    else:
        await state.update_data(selected_task_dict=None)
        logger.debug("selected cert to task")
        selected_cert = free_certs[int(callback.data)]
        logger.debug(f"selected_cert: {selected_cert}")
        await state.set_state(SelectFilesForm.new_task_screen)
        await state.update_data(selected_cert=selected_cert)
        await new_task_screen(callback, state)



@form_router.callback_query(SelectFilesForm.show_user_tasks)
async def show_user_tasks(callback: CallbackQuery, state: FSMContext):
    logger.debug("show_user_tasks")
    data = await state.get_data()

    if callback.data == "go_back":
        await state.set_state(SelectFilesForm.show_user_certs)
        await show_user_certs(callback, state)
        return

    existing_user_tasks = data.get('existing_user_tasks')
    btn_names = []
    btn_values = []
    if existing_user_tasks:
        btn_names += [f"{str(t.get('max_photo_amount'))} фото" for t in existing_user_tasks]
        btn_values += [str(i) for i in range(0, len(existing_user_tasks))]

    btn_names.append("Назад")
    btn_values.append("go_back")

    select_package_kb = await create_kb(btn_names, btn_values)

    await state.update_data(previous_step="show_user_tasks")
    await state.set_state(SelectFilesForm.show_selected_task)
    await callback.message.edit_text(
        text="Выберите ваше задание обработки:", reply_markup=select_package_kb)


@form_router.callback_query(SelectFilesForm.show_selected_task)
async def show_selected_task(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    logger.debug("show_selected_task")
    if callback.data == "go_back":
        await state.update_data(selected_task_dict=None)
        await state.set_state(SelectFilesForm.show_user_certs)
        await show_user_certs(callback, state)
        return
    selected_task_dict = data.get('existing_user_tasks')[int(callback.data)]

    text = (
        f"Статус: {selected_task_dict.get('status')} \n"
        f"Выбранные файлы: "
        f"{str(selected_task_dict.get('files_list')).replace('[]', ' Нет')}"
    )
    callback_labels = []
    callback_data = []
    await state.update_data(selected_task_dict=selected_task_dict)
    if (selected_task_dict.get('max_photo_amount')
            > len(selected_task_dict.get('files_list'))):
        callback_labels.append("Добавить фото")
        callback_data.append("add_photo")
    callback_labels.append("Назад")
    callback_data.append("go_back")
    kb = await create_kb(callback_labels, callback_data)
    await state.set_state(SelectFilesForm.add_photos)
    await callback.message.edit_text(text=text, reply_markup=kb)

    await state.update_data(selected_task_dict=selected_task_dict)
    await state.set_state(SelectFilesForm.process_selected_task)
    await process_selected_task(callback, state)


@form_router.callback_query(SelectFilesForm.process_selected_task)
async def process_selected_task(callback: CallbackQuery, state: FSMContext):
    if callback.data == "go_back":
        await state.set_state(SelectFilesForm.show_user_tasks)
        await show_user_tasks(callback, state)
        return
    if callback.data == "add_photo":
        await state.set_state(SelectFilesForm.add_photos)
        await add_photos(callback, state)
        return


@form_router.callback_query(SelectFilesForm.new_task_screen)
async def new_task_screen(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    logger.debug("new_task_screen")
    selected_cert = data.get('selected_cert')
    logger.debug(f"selected cert: {selected_cert}")
    if callback.data == "go_back":
        await state.update_data(selected_cert=None)
        await state.set_state(SelectFilesForm.show_user_certs)
        await show_user_certs(callback, state)
        return
    await state.set_state(SelectFilesForm.add_photos)
    await add_photos(callback, state)


@form_router.callback_query(SelectFilesForm.add_photos)
async def add_photos(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    logger.debug("add_photos")
    selected_task_dict = data.get('selected_task_dict')
    selected_record_dict = data.get('selected_record_dict')
    selected_cert = data.get('selected_cert')
    client_id = data.get('client_id')
    if callback.data == "go_back":
        await state.update_data(selected_task_dict=None, selected_package=None)
        await state.set_state(SelectFilesForm.show_user_tasks)
        await show_user_tasks(callback, state)
        return
    if not selected_task_dict:
        original_photo_path = await get_record_folder(selected_record_dict)
        checks_result = await check_record_before_create_task(
            selected_record_dict, original_photo_path, client_id)
        await state.update_data(
            original_photo_path=original_photo_path,
            checks_result=checks_result,
        )
        checks_result = {'status': True}

        if checks_result.get('status'):
            await state.set_state(SelectFilesForm.process_digits_set)
            kb = await create_kb(["Назад"], ["go_back"])
            logger.debug(f"selected_cert: {selected_cert}")
            max_photo_amount = (selected_cert.get('type').get('title')
                                .replace("Обработка ", "").replace(" фото", ""))
            await state.update_data(max_photo_amount=max_photo_amount)
            await callback.message.edit_text(
                f"Выберите фото для обработки из Вашей папки\n"
                f"введите через пробел цифровые значения "
                f"из названий до {max_photo_amount} файлов",
                reply_markup=kb
            )
        else:
            await state.update_data(
                selected_task_dict=None,
                selected_package=None,
                previous_step='cert_to_task'
            )
            logger.warning(f"checks_result message: {checks_result.get('message')}")
            await callback.message.edit_text(f"Не удалось создать задачу по обработке",
                                             reply_markup=callback.message.reply_markup)
    else:
        await state.set_state(SelectFilesForm.process_digits_set)
        kb = await create_kb(
            ["Назад"], ["go_back:package_selected"])
        await callback.message.edit_text(
            f"Для Вашей папки выбрано "
            f"{len(selected_task_dict.get('files_list'))} фото"
            f" Введите через пробел цифровые значения "
            f"из названий до "
            f"{selected_task_dict.get('max_photo_amount') - len(selected_task_dict.get('files_list'))} файлов",
            reply_markup=kb)


@form_router.message(SelectFilesForm.process_digits_set)
async def process_digits_set(message: Message, state: FSMContext):
    data = await state.get_data()
    logger.debug("process_digits_set")
    original_photo_path = data.get('original_photo_path')
    checks_result = data.get('checks_result')
    selected_record_dict = data.get('selected_record_dict')
    selected_task_dict = data.get('selected_task_dict')
    selected_cert = data.get('selected_cert')
    max_photo_amount = int(data.get('max_photo_amount')
                        or selected_task_dict.get('max_photo_amount'))

    photos_digits_set = set(message.text.split(" "))
    found_files = set()

    logger.debug(f"photos_digits_set: {photos_digits_set}")

    if len(list(message.text.split(" "))) > max_photo_amount:
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
                        len(found_files) > max_photo_amount):
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
                        'files_list': list(found_files) or [],
                        "client_chat_id": message.chat.id,
                        "yclients_certificate_code": selected_cert.get('number'),
                        "price": selected_task_dict.get('balance')
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
    logger.debug(f"process_digits_set_callback")
    logger.debug(f"prev: {data.get('previous_step')}")
    logger.debug(f"callback data: {callback.data}")

    if "go_back" in callback.data:
        if data.get('previous_step') == "cert_to_task":
            await state.update_data(selected_task_dict=None, selected_cert=None)
            await state.set_state(SelectFilesForm.show_user_certs)
            await show_user_certs(callback, state)
            return
        await state.update_data(selected_task_dict=None, selected_package=None)
        await state.set_state(SelectFilesForm.show_user_tasks)
        await show_user_tasks(callback, state)
        return

