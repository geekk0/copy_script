import configparser
import os
import shutil
import subprocess
import json

from dotenv import load_dotenv
from os import environ

from clients_bot.bot_setup import logger

load_dotenv()
backend_port = environ.get('BACKEND_PORT')
sudo_password = environ.get('SUDOP')

queue_files_mapping = {
    'http://192.168.0.178:8000': 'ai_enhance_queue_ph_1.json',
    'http://192.168.0.199:8000': 'ai_enhance_queue_ph_2.json'
}


async def clear_photo_folder(folder_path):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))


async def prepare_enhance_task(folder: str, files: list):
    logger.debug(f"folder: {folder}, files: {files}")
    demo_folder = folder + '_demo'
    if not os.path.exists(demo_folder):
        os.mkdir(demo_folder)
    for file in files:
        shutil.copy(os.path.join(folder, file), demo_folder)
    await run_indexing(demo_folder)


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


async def add_to_ai_queue(folder, studio_name, demo_mode=False):
    ai_queue_file_path = await get_ai_enhance_queue_file(studio_name)
    ai_index_queue = await get_ai_queue(ai_queue_file_path)

    if not any((task.get("folder_path") == folder and task.get("action") is None) for task in ai_index_queue):
        if demo_mode:
            ai_index_queue.insert(0, {"folder_path": folder, "action": None})
        else:
            ai_index_queue.append({"folder_path": folder, "action": None})
    with open(ai_queue_file_path, 'w') as f:
        json.dump(ai_index_queue, fp=f, indent=4, ensure_ascii=False)


async def get_ai_queue(ai_queue_file_path):
    if not os.path.exists(ai_queue_file_path):
        with open(ai_queue_file_path, 'w') as f:
            json.dump([], fp=f, indent=4, ensure_ascii=False)
            return []

    with open(ai_queue_file_path, 'r') as f:
        return json.load(f)


async def get_ai_enhance_queue_file(studio_name):
    config_file_path = await get_studio_config_file(studio_name)
    settings = await read_settings_file(config_file_path)
    api_url = settings['image_settings']['api_url']
    return f"/cloud/copy_script/{queue_files_mapping[api_url]}"


async def get_studio_config_file(studio):
    studio_configs = {
        'Отражение': 'reflect_config.ini',
        'Портрет(ЗАЛ)': 'portrait_config.ini',
        'Силуэт': 'silhouette_config.ini',
        'Reflect KZ': 'kz_config.ini',
        'test_studio': 'test_studio_config.ini',
        'Neo': 'neo_config.ini',
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


async def remove_demo_folder(folder):
    logger.debug(f"remove_demo_folder folder: {folder}")
    command = f"echo {sudo_password} | sudo -S rm -fr '{folder}'"
    logger.info(command)

    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()

    logger.info(output)

    if process.returncode == 0:
        await run_indexing(os.path.dirname(folder))
