import json
import os

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message, LabeledPrice, InlineKeyboardMarkup,
    InlineKeyboardButton, Document, CallbackQuery, FSInputFile)
from datetime import datetime
from PIL import Image, ImageOps
from dotenv import load_dotenv

from clients_bot.bot_setup import logger, bot
from clients_bot.bot_setup import form_router
from clients_bot.keyboards import create_kb
from clients_bot.api_manager import YClientsAPIManager
from clients_bot.utils import (
    prepare_enhance_task, add_to_ai_queue,
    remove_task_folder, get_folder_files_list)
from clients_bot.enhance_backend_api import EnhanceBackendAPI
from enhance_backend.models import StatusEnum

load_dotenv()
YOOKASSA_PROVIDER_TOKEN = os.getenv("YOOKASSA_PROVIDER_TOKEN")
default_cert_number = os.getenv('DEFAULT_CERT_NUMBER')

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
    process_update_task = State()
    process_all_files = State()
    retouches_settings = State()
    tone_settings = State()
    finalize = State()


studios_mapping = {
    3432916: "Neo", 3843824: "Neo2", 3801061: "Neo2", "Силуэт": "Силуэт", 2843670: "Портрет(ЗАЛ)",
    "Отражение": "Отражение", 2384342: "Отражение", 2684355: "Силуэт"
}

allowed_studios = [3432916, 3843824, 3801061, 2843670, 2384342, 2684355]


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
        await message.answer(text='Введите номер телефона, указанный при бронировании')
        await state.set_state(SelectFilesForm.create_user)


async def format_record_date(date) -> str:
    dt = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%d.%m.%y %H:%M")


async def get_record_folder(record: dict) -> str:
    studio_name = record.get('studio', '')
    date_str = record.get('date', '')
    try:
        date = datetime.strptime(date_str, "%d.%m.%y %H:%M")

        # studio_name = studios_mapping[studio_id]

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


async def check_record_before_create_task(
        folder_path: str,
        selected_task_dict: dict | None = None,
        selected_cert: dict | None = None,
) -> dict:
    result = {'status': True, 'message': None, 'exists': False}

    if not os.path.exists(folder_path):
        result = {'status': False,
                  'message': f'Папка \n"{folder_path}"\n не найдена на сервере', 'exists': False}
        return result

    if selected_cert:
        result = {
            'status': True, 'message': None,
            'exists': False
        }
        return result

    logger.debug(f'selected_cert: {selected_cert}')
    logger.debug(f'selected_task_dict: {selected_task_dict}')
    logger.debug(f'selected_task_dict max_photo_amount: {selected_task_dict.get("max_photo_amount")}')

    max_photo_amount = selected_task_dict.get('max_photo_amount')

    try:
        logger.debug(f"enhanced files count: {selected_task_dict.get('enhanced_files_count')}")
        logger.debug(f"len existing task files_list: {len(selected_task_dict.get('files_list'))}")
        logger.debug(f"max_photo_amount: {max_photo_amount}")
        if max_photo_amount:
            if (selected_task_dict.get('enhanced_files_count') +
                    len(selected_task_dict.get('files_list')) < int(max_photo_amount)):
                result = {
                    'status': True, 'message': None,
                    'exists': True, 'task': selected_task_dict
                }
            else:
                result['status'] = False
                result['message'] = f"Фото уже выбраны для этого сеанса"
        else:
            logger.debug(f"no max_photo_amount")
    except Exception as e:
        logger.error(e)

    return result


async def put_all_photos_to_files_list(folder_path):
    files = [f for f in os.listdir(folder_path)
             if os.path.isfile(os.path.join(folder_path, f))]
    return files


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
    logger.debug(f"phone before: {phone}")
    phone = phone.replace(' ', '').replace('-', '')
    if phone.startswith('8'):
        phone = phone.replace('8', '7', 1)
    if phone.startswith('9'):
        phone = '7' + phone
    if phone.startswith('+7'):
        phone = phone.replace("+", "")
    logger.debug(f"phone after: {phone}")

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
    else:
        await message.answer(f"Клиент с номером телефона: {phone} не найден")


@form_router.message(SelectFilesForm.get_user_records)
async def get_records(message: Message, state: FSMContext):
    data = await state.get_data()
    yclients_user_id = data.get('yclients_user_id')
    result = await api_manager.get_client_records_by_client_id(yclients_user_id)
    records = []

    if not result.get('data'):
        await message.answer(text='Не найдена запись по этому номеру телефона')
        await state.set_state(SelectFilesForm.create_user)
        return

    for record in result.get('data'):
        studio_id = record.get('staff').get('id')
        logger.debug(f'studio_id: {studio_id}')
        if studio_id in allowed_studios:
            record_dict = {
                'record_id': record.get('id'),
                'date': await format_record_date(record.get('date')),
                'studio': studios_mapping[studio_id]
            }
            records.append(record_dict)
        else:
            await message.answer(text="Для этой студии обработка по сертификату "
                                      "пока недоступна. \n Обратитесь к администратору")

    logger.debug(f'records_objects: {records}')

    await state.update_data(records_objects=records)

    record_ids = [str(record.get("record_id")) for record in records]
    record_dates = [record.get("date") for record in records]
    # record_dates = [str(f'{record.get("date")} {str(record.get("studio"))}') for record in records]

    records_kb = await create_kb(record_dates, record_ids)
    await state.set_state(SelectFilesForm.show_user_certs)
    await message.answer(text="Добро пожаловать в Reflect Retouch! Выберите нужную запись", reply_markup=records_kb)


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

    all_existing_user_tasks = await enh_back_api.get_client_tasks(
        client_id)
    logger.debug(f"all_existing_user_tasks: {all_existing_user_tasks}")

    used_cert_numbers = [str(task.get("yclients_certificate_code"))
                         for task in all_existing_user_tasks
                         if task.get("yclients_certificate_code")]

    existing_user_tasks_for_record = [
        task for task in all_existing_user_tasks
        if task.get("yclients_record_id") == selected_record_dict.get("record_id")
    ]

    tasks_for_current_record = [
        task for task in existing_user_tasks_for_record
        if task.get("yclients_record_id") == selected_record_dict.get("record_id")]
    logger.debug(f"tasks_for_current_record: {tasks_for_current_record}")

    user = await enh_back_api.get_user_by_chat_id(callback.message.chat.id)
    all_certs = (await api_manager.get_enhance_certs(user.get('phone_number'))).get('data')
    enhance_certs = [cert for cert in all_certs
                     if cert.get('type').get('title').startswith('Обработка')]
    logger.debug(f"enhance_certs: {enhance_certs}")

    btn_names = []
    btn_values = []

    free_certs = [cert for cert in enhance_certs
                  if cert.get('number') not in used_cert_numbers]

    if free_certs:
        btn_names += [f"{p.get('type').get('title').replace('Обработка ', '')}"
                      for p in free_certs]
        btn_values += [str(i) for i in range(0, len(free_certs))]
        await state.update_data(free_certs=free_certs)

    btn_names.append("Купить")
    btn_values.append("new_package")

    if existing_user_tasks_for_record:
        btn_names.append("В обработке")
        btn_values.append("existing_tasks")
        await state.update_data(existing_user_tasks_for_record=existing_user_tasks_for_record)

    btn_names.append("Назад")
    btn_values.append("go_back")

    client_has_demo = await enh_back_api.check_demo_task_exists(callback.message.chat.id)
    if not client_has_demo:
        btn_names.insert(0, "Бесплатные 10 фото")
        btn_values.insert(0, "demo")

    btn_names.append("AImaEngineBot ")
    btn_values.append("https://t.me/AImaEngineBot")

    select_package_kb = await create_kb(btn_names, btn_values)

    await state.update_data(
        tasks_list=tasks_for_current_record,
        selected_record_dict=selected_record_dict,
    )
    await state.set_state(SelectFilesForm.process_certs_screen)
    try:
        await callback.message.edit_text(
            text="Чтобы приобрести пакет обработки, нажмите кнопку. \n"
                 '"Купить", либо выберите из уже имеющихся пакетов. " \n\n'
                 'Запущенные вами процессы отображаются в разделе "В обработке" '
                 'где вы можете добавить фотографии на обработку.',
            reply_markup=select_package_kb)
    except:
        await callback.message.delete()
        await state.set_state(SelectFilesForm.get_user_records)
        await get_records(message=callback.message, state=state)


@form_router.callback_query(SelectFilesForm.process_certs_screen)
async def process_certs_screen(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_task_dict = data.get('selected_task_dict')
    logger.debug("process_certs_screen")
    logger.debug(f"callback.data: {callback.data}")
    logger.debug(f"selected_task_dict: {selected_task_dict}")
    tasks_list = data.get("existing_user_tasks_for_record")
    client_id = data.get('client_id')
    selected_record_dict = data.get("selected_record_dict")
    free_certs = data.get("free_certs")
    as_new_package = data.get("as_new_package")
    await state.update_data(as_new_package=False)
    if "go_back" in callback.data:
        await state.set_state(SelectFilesForm.show_user_certs)
        await show_user_certs(callback, state)
        return

    elif callback.data == "demo":
        selected_cert = {
            'id': 7134548,
            'number': default_cert_number,
            'balance': 0,
        }
        await state.update_data(
            as_new_package=True,
            selected_cert=selected_cert,
            max_photo_amount=10
        )
        await state.set_state(SelectFilesForm.new_task_screen)
        await new_task_screen(callback, state)
        return

    elif callback.data == "new_package" or as_new_package:
        available_packages = await enh_back_api.get_available_packages()
        logger.debug(f"available_packages: {available_packages}")
        text = (f'Выбор и оплата пакета\n'
                f'После покупки пакета, вернитесь в бота, \n'
                f' нажмите "назад" или команду "/start" и выберите купленный вами пакет обработки')

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

    existing_user_tasks_for_record = data.get('existing_user_tasks_for_record')
    btn_names = []
    btn_values = []
    if existing_user_tasks_for_record:
        for i, task in enumerate(existing_user_tasks_for_record):
            max_photos = task.get('max_photo_amount')
            if max_photos:
                btn_names.append(f"{max_photos} фото")
            else:
                btn_names.append("Все фото")
            btn_values.append(str(i))

    btn_names.append("Назад")
    btn_values.append("go_back")

    select_package_kb = await create_kb(btn_names, btn_values)

    await state.update_data(previous_step="show_user_tasks")
    await state.set_state(SelectFilesForm.show_selected_task)
    await callback.message.edit_text(
        text="В этом разделе вы можете видеть как запущенные вами, так и завершенные, задания по обработке.\n\n"
             'Для того чтобы добавить фото, выберите нужный пакет и нажмите "Добавить фото"',
        reply_markup=select_package_kb)


@form_router.callback_query(SelectFilesForm.show_selected_task)
async def show_selected_task(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    logger.debug("show_selected_task")
    if callback.data == "go_back":
        await state.update_data(selected_task_dict=None)
        await state.set_state(SelectFilesForm.show_user_certs)
        await show_user_certs(callback, state)
        return
    try:
        selected_task_dict = data.get('existing_user_tasks_for_record')[int(callback.data)]
        logger.debug(f"selected_task_dict: {selected_task_dict}")
        callback_labels = []
        callback_data = []
        await state.update_data(selected_task_dict=selected_task_dict)
        if selected_task_dict.get('max_photo_amount'):
            if (selected_task_dict.get('max_photo_amount')
                    > len(selected_task_dict.get('files_list'))):
                callback_labels.append("Добавить фото")
                callback_data.append("add_photo")
            text = (
                f'Номер задания: {selected_task_dict.get("id")} \n'
                f"Статус: {selected_task_dict.get('status')} \n"
                f"Пресет обработки: {selected_task_dict.get('selected_action')} \n"
                f"Выбранные файлы: \n"
                f"{str(selected_task_dict.get('files_list')).strip('[]')}"
            )
        else:
            text = (
                f"Статус: {selected_task_dict.get('status')} \n"
                f"Выбрано файлов: "
                f"{str(len(selected_task_dict.get('files_list')))}"
            )
        callback_labels.append("Назад")
        callback_data.append("go_back")
        kb = await create_kb(callback_labels, callback_data)
        await state.set_state(SelectFilesForm.add_photos)
        await callback.message.edit_text(text=text, reply_markup=kb)

        await state.update_data(selected_task_dict=selected_task_dict)
        await state.set_state(SelectFilesForm.process_selected_task)
        await process_selected_task(callback, state)
    except Exception as e:
        logger.error(f"show_selected_task ERROR: {e}")


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
    if callback.data == "go_back":
        await state.update_data(selected_task_dict=None, selected_package=None)
        await state.set_state(SelectFilesForm.show_user_tasks)
        await show_user_tasks(callback, state)
        return

    original_photo_path = await get_record_folder(selected_record_dict)

    logger.debug(f'original_photo_path: {original_photo_path}')
    logger.debug(f'selected_record_dict: {selected_record_dict}')
    logger.debug(f'add photos selected_task_dict: {selected_task_dict}')

    checks_result = await check_record_before_create_task(
        original_photo_path,
        selected_task_dict,
        selected_cert,
    )

    await state.update_data(
        original_photo_path=original_photo_path,
        checks_result=checks_result,
    )

    logger.debug(f'checks_result: {checks_result}')

    if not checks_result.get('status'):
        await callback.message.answer(f'Папка отсутствует на сервере')
        return

    if not selected_task_dict:
        logger.debug("создаем новую таску")

        if checks_result.get('status'):
            await state.set_state(SelectFilesForm.process_digits_set)
            kb = await create_kb(["Назад"], ["go_back"])
            logger.debug(f"selected_cert: {selected_cert}")
            if data.get('max_photo_amount'):
                max_photo_amount = data.get('max_photo_amount')
            else:
                try:
                    max_photo_amount = str(int((selected_cert.get('type').get('title')
                                                .replace("Обработка ", "").replace(" фото", ""))))
                except Exception as e:
                    logger.error(f"max_photo_amount error: {e}")
                    max_photo_amount = None
            logger.debug(f"max_photo_amount: {max_photo_amount}")

            await state.update_data(max_photo_amount=max_photo_amount)
            if max_photo_amount:
                await callback.message.edit_text(
                    f"Выберите фото для обработки. \n\n"
                    f'- Прикрепите выбранные вами файлы. ❗️Важно прикреплять фотографии именно как файл, '
                    f'а не как изображение.❗️ Затем нажмите кнопку "Готово" \n\n'
                    f'- Так же, вы можете написать в сообщении боту, '
                    f'через запятую цифры из названий файлов, '
                    f"без букв (для примера 988345 988356 988365 987444 ...)\n\n"
                    f"- ❗️ Пожалуйста, внимательно выбирайте номера, после запуска обработки, "
                    f"возможности убрать выбранные вами файлы не будет ❗️ \n\n"
                    f"- Вы можете выбрать меньшее количество файлов, "
                    f"чем указано в вашем пакете, и потом добавить файлы в обработку \n\n"
                    f"- Общее количество обработанных файлов - {max_photo_amount}, согласно выбранному Вами пакету.",
                    reply_markup=kb
                )
            else:
                await state.set_state(SelectFilesForm.process_all_files)
                await process_all_files_callback(callback, state)
                return
        else:
            await state.update_data(
                selected_task_dict=None,
                selected_package=None,
                previous_step='cert_to_task'
            )
            logger.warning(f"checks_result message: {checks_result.get('message')}")
            await callback.message.edit_text(f"Не удалось создать задачу по обработке, "
                                             f"папка отсутствует на сервере",
                                             reply_markup=callback.message.reply_markup)
    else:
        logger.debug('имеется таска')
        await state.update_data(original_photo_path=selected_task_dict.get('folder_path'))
        await state.set_state(SelectFilesForm.process_digits_set)
        kb = await create_kb(
            ["Назад"], ["go_back:package_selected"])
        await callback.message.edit_text(
            f"Для Вашей папки выбрано "
            f"{len(selected_task_dict.get('files_list'))} фото \n"
            f"Вы можете добавить фото отправив их как документ\n"
            f"Или ввести через пробел цифровые значения "
            f"из названий до "
            f"{selected_task_dict.get('max_photo_amount') - len(selected_task_dict.get('files_list'))} файлов",
            reply_markup=kb)


@form_router.message(SelectFilesForm.process_digits_set, F.text)
async def process_digits_set(message: Message, state: FSMContext):
    data = await state.get_data()
    logger.debug("process_digits_set")
    original_photo_path = data.get('original_photo_path')
    checks_result = data.get('checks_result')
    selected_record_dict = data.get('selected_record_dict')
    selected_task_dict = data.get('selected_task_dict')
    selected_cert = data.get('selected_cert')
    max_photo_amount = int(data.get('max_photo_amount') or selected_task_dict.get('max_photo_amount'))

    photos_digits_set = set(message.text.split(" "))
    found_files = set()

    logger.debug(f"checks_result: p_d_s {checks_result}")

    logger.debug(f"photos_digits_set: {photos_digits_set}")

    logger.debug(f'selected photos len: {len(list(message.text.split(" ")))}')
    logger.debug(f'max_photo_amountL {max_photo_amount}')
    logger.debug(f'selected_task_dict: {selected_task_dict}')

    existing_photos = len(selected_task_dict.get('files_list')) if selected_task_dict else 0

    logger.debug(f'existing_photos: {existing_photos}')

    if len(list(message.text.split(" "))) + existing_photos > max_photo_amount:
        await message.answer("Количество фото превышено")
        return

    logger.debug(f'original_photo_path: {original_photo_path}')

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
        logger.debug(f'checks_result: {checks_result}')
        task_data = None
        if checks_result.get('exists'):
            existing_task = checks_result.get('task')

            try:
                existing_files = set(existing_task.get('files_list') or [])
                new_unique_files = list(found_files - existing_files)

                if not new_unique_files:
                    await message.answer("Выбранные файлы уже добавлены в обработку.")
                    return

                if existing_task.get('enhanced_files_count', 0) + len(new_unique_files) > max_photo_amount:
                    await message.answer("Общее количество выбранных фото превышено")
                    return

                existing_task['files_list'] = list(existing_files | set(new_unique_files))
                await state.update_data(updating_task=existing_task)
                update_task_kb = await create_kb(
                    ['Настроить', 'Готово'], ['select_preset', 'finalize'])

                await state.set_state(SelectFilesForm.process_update_task)

                await message.answer(
                    f"Выбраны для обработки:\n"
                    f"{' '.join(map(str, existing_task.get('files_list')))}\n",
                    reply_markup=update_task_kb
                )
                return
            except Exception as e:
                logger.error(e)

            task_data = existing_task
            await state.update_data(task_data=task_data, task_status='update')

        else:
            task_data = {
                'folder_path': original_photo_path,
                'yclients_record_id': int(selected_record_dict.get('record_id')),
                'files_list': list(found_files) or [],
                "client_chat_id": message.chat.id,
                "yclients_certificate_code": selected_cert.get('number'),
                "price": selected_cert.get('balance'),
                "max_photo_amount": max_photo_amount,
                "status": StatusEnum.QUEUED.value
            }
            logger.debug(f"task_data: {task_data}")

            await state.update_data(task_data=task_data, task_status='create')
            await retouches_settings(message, state)

        logger.debug(f'task_data: {task_data}')


@form_router.message(SelectFilesForm.process_digits_set, F.document)
async def handle_select_photos_as_docs(message: Message, state: FSMContext):
    data = await state.get_data()
    document: Document = message.document
    file_name = document.file_name
    handled_media_groups = data.get('handled_media_groups', [])
    selected_task_dict = data.get('selected_task_dict')
    original_photo_path = data.get('original_photo_path')
    selected_files = data.get('selected_files') or []
    logger.debug(f'input selected_files: {selected_files}')
    max_photo_amount = int(data.get('max_photo_amount')
                           or selected_task_dict.get('max_photo_amount'))
    existing_photos = len(selected_task_dict.get('files_list')) \
        if selected_task_dict else 0

    files_folder = (original_photo_path or
                    selected_task_dict.get('folder_path'))

    directory_files_list = (data.get('directory_files_list', None)
                            or await get_folder_files_list(files_folder))
    logger.debug(f'directory_files_list: {directory_files_list}')

    if not document.mime_type.startswith("image/"):
        await message.reply("Файл должен быть изображением.")
        return

    if file_name not in directory_files_list:
        await message.reply(f'Файл "{file_name}" не найден в папке.')
        return
    elif len(selected_files) + existing_photos > max_photo_amount:
        await message.reply(f'Количество файлов превышено')
        return
    else:
        if file_name not in selected_files:
            selected_files.append(file_name)
        await state.update_data(selected_files=selected_files)

    logger.debug(f'output selected_files: {selected_files}')

    media_group_id = message.media_group_id
    if not media_group_id or media_group_id not in handled_media_groups:
        handled_media_groups.append(media_group_id)
        await state.update_data(handled_media_groups=handled_media_groups)
        kb = await create_kb(
            ['Готово', 'Назад'],
            ['all_files_selected', 'go_back']
        )
        await message.answer("Файлы добавлены", reply_markup=kb)


@form_router.callback_query(SelectFilesForm.process_digits_set)
async def process_selected_photos_as_docs(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_task_dict = data.get('selected_task_dict')
    selected_files = data.get('selected_files')
    original_photo_path = data.get('original_photo_path')
    checks_result = data.get('checks_result')
    selected_record_dict = data.get('selected_record_dict')
    selected_cert = data.get('selected_cert')
    if callback.data == "go_back":
        await state.update_data(selected_files=None)
        await state.set_state(SelectFilesForm.show_user_certs)
        await show_user_certs(callback, state)
        return

    elif callback.data == "all_files_selected":
        logger.debug(f'all_files_selected')
        try:
            max_photo_amount = int(
                data.get('max_photo_amount') or
                selected_task_dict.get('max_photo_amount'))
        except Exception as e:
            logger.error(e)
        logger.debug(f'selected_task_dict: {selected_task_dict}')
        # if selected_task_dict:
        #     selected_task_dict['files_list'] += selected_files
        if checks_result.get('exists'):
            existing_task = checks_result.get('task')

            try:
                existing_files = set(existing_task.get('files_list') or [])
                logger.debug(f'existing_files: {existing_files}')
                logger.debug(f'selected_files: {selected_files}')
                new_unique_files = list(set(selected_files) - existing_files)

                if not new_unique_files:
                    await callback.message.answer("Выбранные файлы уже добавлены в обработку.")
                    return

                if existing_task.get('enhanced_files_count', 0) + len(new_unique_files) > max_photo_amount:
                    await callback.message.answer("Общее количество выбранных фото превышено")
                    return

                existing_task['files_list'] = list(existing_files | set(new_unique_files))
            except Exception as e:
                logger.error(e)
            logger.debug(f'existing_task files check')
            await state.update_data(updating_task=existing_task)
            await state.set_state(SelectFilesForm.process_update_task)

            try:
                update_task_kb = await create_kb(
                    ['Настроить', 'Готово'], ['select_preset', 'finalize'])
                await callback.message.answer(
                    f"Выбраны для обработки:\n"
                    f"{' '.join(map(str, existing_task.get('files_list')))}\n",
                    reply_markup=update_task_kb
                )
            except Exception as e:
                logger.error(e)

            # await retouches_settings(callback.message, state)


        else:
            task_data = {
                'folder_path': original_photo_path,
                'yclients_record_id': int(selected_record_dict.get('record_id')),
                'files_list': list(selected_files) or [],
                "client_chat_id": callback.message.chat.id,
                "yclients_certificate_code": selected_cert.get('number'),
                "price": selected_cert.get('balance'),
                "max_photo_amount": max_photo_amount,
                "status": StatusEnum.QUEUED.value
            }
            logger.debug(f"task_data: {task_data}")

            await state.update_data(task_data=task_data, task_status='create')
            await retouches_settings(callback.message, state)


@form_router.callback_query(SelectFilesForm.process_update_task)
async def process_update_task(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    logger.debug('process_update_task')
    logger.debug(f'updating_task: {data.get("updating_task")}')
    if data.get('updating_task'):
        if callback.data == "select_preset":
            await state.set_state(SelectFilesForm.retouches_settings)
            await retouches_settings(message=callback.message, state=state)
        elif callback.data == "finalize":
            await state.set_state(SelectFilesForm.finalize)
            await finalize(callback, state)


@form_router.message(SelectFilesForm.retouches_settings)
async def retouches_settings(message: Message, state: FSMContext):
    await state.update_data(selected_files=None)
    data = await state.get_data()
    task_data = data.get('task_data')
    task_status = data.get('task_status')
    logger.debug('retouches_settings')
    logger.debug(f'task_data: {task_data}, task_status: {task_status}')

    retouches_select_photos = {
        'Hard': 'hard_normal.jpg',
        'Normal': 'normal_normal.jpg',
        'Light': 'light_normal.jpg'
    }

    try:
        for setting, filename in retouches_select_photos.items():
            photo = FSInputFile(f"/cloud/copy_script/clients_bot/photos/{filename}")
            await message.answer_photo(photo, caption=setting)
    except Exception as e:
        logger.error(e)

    settings_kb = await create_kb(
        list(retouches_select_photos.keys()),
        list(retouches_select_photos.keys()))

    await state.set_state(SelectFilesForm.tone_settings)
    await message.answer('Выберите настройку ретуши', reply_markup=settings_kb)


@form_router.callback_query(SelectFilesForm.tone_settings)
async def tone_settings(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    retouches_setting = callback.data

    logger.debug('tone_settings')
    logger.debug(f'retouches_setting: {retouches_setting}')

    await state.update_data(retouches_setting=retouches_setting)

    tone_select_photos_mapping = {
        'Light': {
            'Cold': 'light_cold.jpg',
            'Normal': 'light_normal.jpg',
            'Warm': 'light_warm.jpg'
        },
        'Normal': {
            'Cold': 'normal_cold.jpg',
            'Normal': 'normal_normal.jpg',
            'Warm': 'normal_warm.jpg'
        },
        'Hard': {
            'Cold': 'hard_cold.jpg',
            'Normal': 'hard_normal.jpg',
            'Warm': 'hard_warm.jpg'
        }
    }

    try:
        for setting, filename in tone_select_photos_mapping[retouches_setting].items():
            photo = FSInputFile(f"/cloud/copy_script/clients_bot/photos/{filename}")
            await callback.message.answer_photo(photo, caption=setting)
    except Exception as e:
        logger.error(e)

    settings_kb = await create_kb(
        list(tone_select_photos_mapping[retouches_setting].keys()),
        list(tone_select_photos_mapping[retouches_setting].keys()))

    await state.set_state(SelectFilesForm.finalize)
    await callback.message.answer('Выберите настройку тона', reply_markup=settings_kb)


@form_router.callback_query(SelectFilesForm.finalize)
async def finalize(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    logger.debug('finalize')
    updating_task = data.get("updating_task")

    retouches_setting = data.get('retouches_setting')
    task_data = data.get('task_data')
    original_photo_path = data.get('original_photo_path')
    selected_record_dict = data.get('selected_record_dict')
    tone_setting = callback.data

    action_name = f'{retouches_setting}_{tone_setting}'.lower()

    logger.debug(f'original_photo_path: {original_photo_path}')
    logger.debug(f'default_cert_number: {default_cert_number}')

    if updating_task:
        task_data = updating_task

    if task_data.get('yclients_certificate_code') == default_cert_number:
        demo_task = True
    else:
        demo_task = False

    if updating_task:
        logger.debug(f'updating_task found')
        updating_task_data = updating_task
        if 'finalize' in callback.data:
            action_name = updating_task_data['selected_action']
        else:
            action_name = f'{retouches_setting}_{tone_setting}'.lower()

        sending_task_data = {
            'files_list': updating_task_data.get('files_list'),
            'status': StatusEnum.QUEUED.value,
            'selected_action': action_name
        }

        await enh_back_api.update_enhance_task(
            task_id=updating_task_data.get('id'),
            task_data=sending_task_data
        )

        try:
            try:
                await prepare_enhance_task(
                    updating_task_data.get('folder_path'),
                    sending_task_data.get('files_list'),
                    updating_task_data.get('yclients_certificate_code')
                )
            except Exception as e:
                logger.error(f"error prepare_enhance_task: {e}")

            await add_to_ai_queue(
                folder=original_photo_path + "_task_" + str(
                    updating_task_data.get('yclients_certificate_code')),
                studio_name=selected_record_dict.get('studio'),
                task_mode=True,
                action=action_name
            )

            files_list = updating_task_data.get('files_list')

            await state.update_data(selected_cert=None, updating_task_data=None, task_data=None)

            await callback.message.answer(
                f"Выбраны для обработки:\n"
                f"{' '.join(map(str, files_list))}\n"
                f"Фото добавлены в очередь, мы сообщим Вам как только они обработаются"
            )

        except Exception as e:
            logger.error(e)
        return

    logger.debug(f'task_data: {task_data}')
    logger.debug(f'action_name: {action_name}')

    task_data['selected_action'] = action_name

    task_data = await enh_back_api.add_enhance_task(
        task_data=task_data
    )
    logger.debug(f"created task: {task_data}")

    # действия по таске

    if data.get('all_files_selected'):
        try:
            new_folder_name = original_photo_path + "_task_" + str(
                task_data.get('yclients_certificate_code')) + '_renamed'
            os.rename(original_photo_path, new_folder_name)
            await add_to_ai_queue(
                new_folder_name,
                selected_record_dict.get('studio'),
                True,
                action_name
            )
        except Exception as e:
            logger.error(f"error add_to_ai_queue: {e}")

    else:
        try:
            await prepare_enhance_task(
                original_photo_path,
                task_data.get('files_list'),
                task_data.get('yclients_certificate_code')
            )
        except Exception as e:
            logger.error(f"error prepare_enhance_task: {e}")
        try:
            await add_to_ai_queue(
                original_photo_path + "_task_" + str(task_data.get('yclients_certificate_code')),
                selected_record_dict.get('studio'),
                True,
                action_name
            )
            logger.debug(f"task_id: {task_data.get('id')}, status: {StatusEnum.QUEUED.value}")
        except Exception as e:
            logger.error(f"error add_to_ai_queue: {e}")

    await enh_back_api.change_task_status(
        task_data.get('yclients_certificate_code'),
        StatusEnum.QUEUED.value,
        folder_path=original_photo_path,
        demo_task=demo_task
    )
    await state.update_data(selected_cert=None, updating_task_data=None, task_data=None)

    message_text = (f"Фото добавлены в очередь, мы сообщим Вам как только они обработаются\n"
                    f"Выбраны для обработки: ")

    if data.get('all_files_selected'):
        message_text += "Все"
        await state.update_data(all_files_selected=False)
    else:
        message_text += " ".join(map(str, task_data.get('files_list')))

    await callback.message.answer(message_text)
    await state.clear()


@form_router.callback_query(SelectFilesForm.process_all_files)
async def process_all_files_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    logger.debug(f"process_all_files_callback 1")
    logger.debug(f"callback data: {callback.data}")
    original_photo_path = data.get('original_photo_path')
    selected_record_dict = data.get('selected_record_dict')
    selected_cert = data.get('selected_cert')

    try:
        files_list = await put_all_photos_to_files_list(original_photo_path)
    except Exception as e:
        logger.error(f"files_list error: {e}")

    logger.debug(f"files_list: {str(len(files_list))}")

    task_data = {
        'folder_path': original_photo_path,
        'yclients_record_id': int(selected_record_dict.get('record_id')),
        'files_list': files_list,
        "client_chat_id": callback.message.chat.id,
        "yclients_certificate_code": selected_cert.get('number'),
        "price": selected_cert.get('balance'),
        "max_photo_amount": None,
        "status": StatusEnum.QUEUED.value
    }
    # logger.debug(f"task_data: {task_data}")
    # new_task = await enh_back_api.add_enhance_task(
    #     task_data=task_data
    # )
    # logger.debug(f"created task: {new_task}")
    #
    # try:
    #     await prepare_enhance_task(
    #         original_photo_path,
    #         files_list,
    #         task_data.get('yclients_certificate_code')
    #     )
    # except Exception as e:
    #     logger.error(f"error prepare_enhance_task: {e}")
    # logger.debug(f"original_photo_path: {original_photo_path}")
    # await add_to_ai_queue(
    #     original_photo_path + "_task",
    #     studios_mapping[selected_record_dict.get('studio')],
    #     True
    # )
    # await enh_back_api.change_task_status(new_task.get('id'), StatusEnum.QUEUED.value)
    #
    # await callback.message.answer(
    #     f"Все фото из папки добавлены в очередь \n"
    #     f"мы сообщим Вам как только они обработаются")
    await state.update_data(all_files_selected=True, task_data=task_data)
    await state.set_state(SelectFilesForm.retouches_settings)
    await retouches_settings(callback.message, state)


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

