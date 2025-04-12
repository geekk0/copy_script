import os
import asyncio
import subprocess
import configparser
import pwd
import grp
import json
import time
import requests

from os import environ
from dotenv import load_dotenv
from bs4 import BeautifulSoup

from .bot_setup import logger

load_dotenv()

sudo_password = environ.get('SUDOP')

queue_files_mapping = {
    'http://192.168.0.178:8000': 'ai_enhance_queue_ph_1.json',
    'http://192.168.0.199:8000': 'ai_enhance_queue_ph_2.json'
}


async def run_indexing(path):
    path = path.replace('/cloud', '')
    command = f"echo {sudo_password} | sudo -S -u www-data php /var/www/cloud/occ files:scan -p '{path}' --shallow"
    path = os.path.dirname(path)
    logger.info(command)

    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()

    logger.info(output)

    if process.returncode == 0:
        return "Индексация произведена успешно"

    else:
        return "Ошибка индексации"


async def check_ready_for_index(path):
    initial_count = await count_files_in_folder(path)
    await asyncio.sleep(5)
    final_count = await count_files_in_folder(path)
    if final_count == initial_count:
        return True


async def count_files_in_folder(folder_path):
    count = 0
    for root, dirs, files in os.walk(folder_path):
        count += len(files)
    return count


async def get_studio_config_file(studio):
    studio_configs = {
        'Отражение': 'reflect_config.ini',
        'Портрет(ЗАЛ)': 'portrait_config.ini',
        'Силуэт': 'silhouette_config.ini',
        'Reflect KZ': 'kz_config.ini',
        'test_studio': 'test_studio_config.ini',
        'Neo': 'neo_config.ini',
        'Neo2': 'neo2_config.ini',
        'Милан': 'milan_config.ini'
    }

    studio_config_file_path = (os.path.join(f'/cloud/copy_script',
                                            studio_configs[studio]))

    if os.path.exists(studio_config_file_path):
        return studio_config_file_path
    else:
        logger.error(f'config file not found: {studio_config_file_path}')


async def read_settings_file(settings_file):
    with open(settings_file, 'r', encoding='utf-8') as file:
        config = configparser.ConfigParser()
        config.read_file(file)
        path_settings = config['Settings']
        if config.has_section('ImageEnhancement'):
            image_settings = config['ImageEnhancement']
            return {'path_settings': path_settings, 'image_settings': image_settings}
        else:
            return {'path_settings': path_settings}


async def change_ownership(path, user='www-data', group='www-data'):
    command = f'sudo chown -R www-data:www-data "{path}"'
    os.system(command)


async def change_folder_permissions(folder):
    command = f'sudo chmod -R g+w "{folder}"'
    os.system(command)


async def validation_settings_value(parameter, old_value, new_value):
    if 'filter' in parameter:
        if new_value.lower() == 'true' or new_value.lower() == 'false':
            return True
        else:
            return "Новое значение должно быть True или False"
    elif is_float(old_value):
        if is_float(new_value):
            return True
        else:
            return "Новое значение должно быть числом"
    return True


def is_float(value):
    try:
        float(value)  # Try converting the value to a float
        return True
    except ValueError:
        return False


async def write_settings_file(config_file, key, value):
    config = configparser.ConfigParser()
    config.read(config_file)
    config.set('ImageEnhancement', key, value)

    with open(config_file, 'w', encoding='utf-8') as file:
        config.write(file)


async def add_to_ai_queue(folder, studio_name, action=None):
    ai_queue_file_path = await get_ai_enhance_queue_file(studio_name)
    ai_index_queue = await get_ai_queue(ai_queue_file_path)

    action_mapping = {"black-white": "milan_1_bw", "regular": None}

    if studio_name == "Милан":
        action = action_mapping.get(action, None)

    if not any((task.get("folder_path") == folder and task.get("action") == action) for task in ai_index_queue):
        if studio_name == "Милан":
            ai_index_queue.append({"folder_path": folder, "action": action})
        else:
            ai_index_queue.insert(0, {"folder_path": folder, "action": action})
    with open(ai_queue_file_path, 'w') as f:
        json.dump(ai_index_queue, fp=f, indent=4, ensure_ascii=False)


async def get_ai_queue(ai_queue_file_path):
    if not os.path.exists(ai_queue_file_path):
        with open(ai_queue_file_path, 'w') as f:
            json.dump([], fp=f, indent=4, ensure_ascii=False)
            return []

    with open(ai_queue_file_path, 'r') as f:
        # logger.info(json.load(f))
        return json.load(f)


async def run_rs_enhance(folder_path):
    logger.info(f"Running RS enhance for folder: {folder_path}")

    studio_name = folder_path.split("/")[4]

    config_file_mapping = {
        'Силуэт': 'silhouette_config.ini',
        'Отражение': 'reflect_config.ini',
        'Reflect KZ': 'kz_config.ini',
        'Neo': 'neo_config.ini',
        'Портрет(ЗАЛ)': 'portrait_config.ini'
    }

    hour_range = folder_path.split("/")[-1]
    screen_session_name = f"enhance_folder_{studio_name}_{hour_range}"

    config_file_name = config_file_mapping.get(studio_name, None)
    if not config_file_name:
        logger.error(f"Studio '{studio_name}' not found in the mapping.")
        return

    try:
        result = subprocess.run(["/cloud/copy_script/tg_bot_aio/bot/enhance_folder_script.sh",
                                 screen_session_name,
                                 sudo_password,
                                 config_file_name,
                                 folder_path],
                                check=True, capture_output=True, text=True)
        logger.info(f"RS enhance started. returncode: {result.returncode}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing command: {e}")


async def share_video(name):
    username = environ.get('username')
    password = environ.get('password')

    share_request = requests.Request('POST',
                                     f'https://cloud.reflect-studio.ru/ocs/v2.php/apps/files_sharing/api/v1/shares',
                                     headers={'OCS-APIRequest': 'true'},
                                     data={'path': f'Videos_sharing/{name}', 'shareType': '3', 'permissions': '1'},
                                     auth=(username, password))

    prepared_request = share_request.prepare()

    try:
        response = requests.Session().send(prepared_request)

        logger.info(f'response: {response.status_code}, {response.text}')

        url = await parse_sharing(response)
        if url:
            return await format_video_url(url, name)
    except Exception as e:
        logger.error(f'Error sending share request: {e}, name: {name}')
        return False


async def parse_sharing(response):
    if response.status_code != 200:
        return False
    soup = BeautifulSoup(response.content, 'xml')

    url_tag = soup.find('url')
    if url_tag is not None:
        url_value = url_tag.text
        return f'{url_value}'


async def format_video_url(url, name):
    return f'{url}/download/{name}'


async def get_ai_enhance_queue_file(studio_name):
    config_file_path = await get_studio_config_file(studio_name)
    settings = await read_settings_file(config_file_path)
    api_url = settings['image_settings']['api_url']
    return f"/cloud/copy_script/{queue_files_mapping[api_url]}"


async def get_readable_queue(queue_file):
    queue_file_path = os.path.join('/cloud/copy_script/', queue_file)
    logger.info(f"queue_file_path: {queue_file_path}")
    with open(queue_file_path, 'r') as f:
        readable_queue_list = [folder for folder in json.load(f)]
        return readable_queue_list


async def remove_from_ai_queue(folder_path, action, queue_file):
    try:
        logger.info(f"folder_path: {folder_path}, action: {action}, queue_file: {queue_file}")
        queue = await get_readable_queue(queue_file)
        logger.info(f"queue: {queue}")
        new_queue = [x for x in queue if not (x.get('folder_path') == folder_path and x.get('action') == action)]
        logger.info(f"new_queue: {new_queue}")
        logger.info(f"exists: {os.path.exists(os.path.join('/cloud/copy_script/', queue_file))}")
        with open(os.path.join('/cloud/copy_script/', queue_file), 'w') as f:
            json.dump(new_queue, fp=f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(e)


async def ai_caller_restart():
    command = f"echo {sudo_password} | sudo -S service ai_enhance_caller restart"
    logger.info(command)
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()

    logger.info(output)
    if process.returncode == 0:
        return "Сервис перезапущен"

    else:
        return "Ошибка перезапуска сервиса"

