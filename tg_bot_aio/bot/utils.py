import os
import asyncio
import subprocess
import configparser
import pwd
import grp
import json
import time


from os import environ
from dotenv import load_dotenv

from .bot_setup import logger

load_dotenv()

sudo_password = environ.get('SUDOP')

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
    directory_path = path
    try:
        uid = pwd.getpwnam(user).pw_uid
        gid = grp.getgrnam(group).gr_gid

        while directory_path != '/':
            os.chown(directory_path, uid, gid)
            directory_path = os.path.dirname(directory_path)

        logger.info(f"Ownership successfully changed")

    except Exception as e:
        logger.error(f"Error changing ownership of '{directory_path}' and its parent directories: {e}")


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


async def add_to_ai_queue(folder):
    ai_index_queue = await get_ai_queue()
    print(ai_index_queue)
    if folder in ai_index_queue:
        print('Already in queue')
        return
    ai_index_queue.insert(0, folder)
    with open('/cloud/copy_script/ai_enhance_queue.json', 'w') as f:
        json.dump(ai_index_queue, f)


async def get_ai_queue():
    file_path = '/cloud/copy_script/ai_enhance_queue.json'
    if not os.path.exists(file_path):
        with open(file_path, 'w') as f:
            json.dump([], f)
            return []
    with open(file_path, 'r') as f:
         return json.load(f)


async def run_rs_enhance(folder_path):
    studio_name = folder_path.split("/")[3]

    config_file_mapping = {
        'Силуэт': 'silhouette_config.ini',
        'Отражение': 'reflect_config.ini',
        'Reflect KZ': 'kz_config.ini'
    }

    hour_range = folder_path.split("/")[-1]
    screen_session_name = f"enhance_folder_{studio_name}_{hour_range}"

    config_file_name = config_file_mapping.get(studio_name, None)
    if not config_file_name:
        print(f"Studio '{studio_name}' not found in the mapping.")
        return

    try:
        password_bytes = sudo_password.encode("utf-8")
        subprocess.run(["sudo", "-i"], input=password_bytes, check=True)
        subprocess.run(["screen", "-S", screen_session_name], check=True)
        subprocess.run(["cd", "/cloud/copy_script"], check=True)
        subprocess.run(["source", "cs_env/bin/activate"], check=True)
        subprocess.run(["python", "enhance_folder.py", config_file_name, folder_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")

