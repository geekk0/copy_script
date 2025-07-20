import os
import json
import signal
import subprocess
import time
from enum import Enum

import pytz
import requests
import threading

from configparser import ConfigParser
from loguru import logger
from datetime import datetime
from dotenv import load_dotenv
from os import environ

from photos_copy_script import FileCopier, read_config
from tg_bot_aio.bot.utils import sudo_password

exclusive_lock = threading.Lock()
stop_event = threading.Event()

load_dotenv()
backend_port = environ.get('BACKEND_PORT')
default_cert_number = environ.get('DEFAULT_CERT_NUMBER')


class StatusEnum(str, Enum):
    PENDING = "Задача создана"
    QUEUED = "Обработка добавлена в очередь"
    PROCESSING = "Идет обработка"
    COMPLETED = "Обработка завершена"
    FAILED = "Ошибка обработки"


enhancer_host_list = [
    'http://192.168.0.178:8000',
    'http://192.168.0.199:8000'
]

config_file_mapping = {
                'Силуэт': 'silhouette_config.ini',
                'Отражение': 'reflect_config.ini',
                'Reflect KZ': 'kz_config.ini',
                'Neo': 'neo_config.ini',
                'Neo2': 'neo2_config.ini',
                'Портрет(ЗАЛ)': 'portrait_config.ini',
                'Милан': 'milan_config.ini'
            }

queue_files_mapping = {
    'http://192.168.0.178:8000': 'ai_enhance_queue_ph_1.json',
    'http://192.168.0.199:8000': 'ai_enhance_queue_ph_2.json'
}


class EnhanceCaller:
    def __init__(self, settings, base_path=None, ps_host=None, bound_logger=None):
        self.studio = settings['path_settings']['Studio_name']
        self.photos_path = settings['path_settings']['BaseDirPath']
        self.files_extension = settings['path_settings']['FileExtension']
        self.studio_timezone = pytz.timezone(settings['path_settings']['TimeZoneName'])
        self.api_url = settings['enhance_settings']['api_url']
        self.action = settings['enhance_settings']['action']
        self.base_path = base_path or os.getcwd()
        self.config = settings
        self.ai_queue_file = os.path.join(self.base_path, queue_files_mapping[self.api_url])
        self.ps_host = ps_host
        self.bound_logger = bound_logger

    def run(self):

        if ("Neo" not in self.studio) and (self.studio != "Портрет(ЗАЛ)"):
            if not os.path.exists(self.photos_path):
                self.bound_logger.error(f'Folder {self.photos_path} does not exist')
                return
            today_folders = self.get_ready_folders_list()

            self.bound_logger.debug(f'studio "{self.studio}": today_folders: {today_folders}')

            self.index_ready_folders(today_folders)

            for folder in today_folders:
                self.add_to_ai_queue(folder)

        self.run_ai_enhance_queue()

    def index_ready_folders(self, ready_folders):
        for folder in ready_folders:
            try:
                self.chown_folder(folder)
                self.index_folder(folder)
            except Exception as e:
                self.bound_logger.error(f'studio "{self.studio}": Error indexing folder {folder}: {e}')

    def enhance_folder(self, folder, action):

        self.bound_logger.debug(f'start enhance folder for {folder}')

        if not os.path.exists(folder):
            self.bound_logger.error(f'folder {folder} does not exist')
            return

        enhance_folder_url = self.api_url + "/enhance_folder/"

        data = {
            "studio_name": folder.split('/')[-4],
            "action_name": action,
            "month": folder.split('/')[-3],
            "day": folder.split('/')[-2],
            "hour": folder.split('/')[-1],
            "task": False
        }

        logger.debug(f'data["hour"]: {data["hour"]}')
        renamed = False

        if "_task" in data["hour"]:
            client_cert_code = data["hour"].split("_task_")[1]
            data["hour"] = data["hour"].split("_task")[0]
            data["task"] = True
            if client_cert_code:
                data['cert_code'] = client_cert_code
                demo_task = default_cert_number in client_cert_code
                if '_renamed' in client_cert_code:
                    renamed = True
                    send_folder_status_to_backend(
                        client_cert_code.replace('_renamed', ''),
                        StatusEnum.PROCESSING.value,
                        demo_task=demo_task,
                        folder_path=folder
                    )
                else:
                    send_folder_status_to_backend(
                        client_cert_code, StatusEnum.PROCESSING.value, demo_task=demo_task, folder_path=folder)

        self.bound_logger.debug(f'studio "{self.studio}": data: {data}')
        self.bound_logger.debug(f'call for route: {enhance_folder_url}')

        response = requests.post(enhance_folder_url, json=data)

        self.bound_logger.debug(f'web enhancer response: {response.json()}')

        if response.status_code != 200:
            if 'already exists' not in response.json().get('error_message'):
                self.bound_logger.error(f"studio {self.studio}: Error occurred: {response.json().get('error_message')}")

        elif response.json().get('error'):
            self.bound_logger.error(f"studio {self.studio}: Error occurred: {response.json().get('error_message')}")


        else:

            self.bound_logger.debug(f"response data: {response.json()}")
            result_folder_name = response.json().get('folder_name')

            if renamed:
                old_folder_name = folder.split("_")[0]
                os.rename(folder, old_folder_name)
                new_result_folder_name = result_folder_name.replace('_renamed', '')
                upper_level_folder = os.path.dirname(folder)
                self.remove_from_ai_queue(folder)
                os.rename(os.path.join(upper_level_folder, result_folder_name),
                          os.path.join(upper_level_folder, new_result_folder_name))
                self.index_folder(upper_level_folder)
                self.index_folder(new_result_folder_name)
                result_folder_name = new_result_folder_name
                self.bound_logger.debug(f'client_cert_code: {client_cert_code}')

                cert_number = client_cert_code.replace('_renamed', '')
                demo_task = default_cert_number == client_cert_code
                folder_path = folder.split("_task_")[0]
                self.bound_logger.debug(f'client_cert_code: {cert_number}')
                send_folder_status_to_backend(
                    cert_number,
                    StatusEnum.COMPLETED.value,
                    completed=True,
                    folder_path=folder_path
                )
            elif "_task" in result_folder_name:
                self.bound_logger.debug(f'remove_folder: {folder}')
                self.remove_task_folder(folder)
                demo_task = default_cert_number == client_cert_code
                folder_path = folder.split("_task_")[0]
                send_folder_status_to_backend(
                    client_cert_code,
                    StatusEnum.COMPLETED.value,
                    demo_task=demo_task,
                    completed=True,
                    folder_path=folder_path
                )
            try:
                self.remove_from_processed_folders(folder)
            except Exception as e:
                self.bound_logger.error(e)
            return result_folder_name

    def get_folder_action(self, folder):

        try:
            folder_task = [d for d in self.get_ai_queue() if d.get("folder_path") == folder][0]
            action = folder_task.get('action')
            if action:
                return action

            if folder.split('/')[-4] == self.studio:
                return self.action

            folder_config_file = config_file_mapping[folder.split('/')[-4]]

            action = read_settings_file(
                os.path.join(os.getcwd(), folder_config_file))['enhance_settings'].get('action')

            return action
        except Exception as e:
            self.bound_logger.error(f'studio "{self.studio}": Error get_folder_action: {e}')

    def add_to_ai_queue(self, folder, action=None):
        ai_index_queue = self.get_ai_queue()

        if not any(task.get("folder_path") == folder for task in ai_index_queue):
            ai_index_queue.append({"folder_path": folder, "action": action})

        with open(self.ai_queue_file, 'w') as f:
            json.dump(ai_index_queue, fp=f, indent=4, ensure_ascii=False)

    def get_ai_queue(self):
        if not os.path.exists(self.ai_queue_file):
            with open(self.ai_queue_file, 'w') as f:
                json.dump([], fp=f, indent=4, ensure_ascii=False)
                return []
        with open(self.ai_queue_file, 'r') as f:
            return json.load(f)

    def remove_from_ai_queue(self, folder):
        ai_index_queue = self.get_ai_queue()
        ai_index_queue = [d for d in ai_index_queue if d.get("folder_path") != folder]
        with open(self.ai_queue_file, 'w') as f:
            json.dump(ai_index_queue, fp=f, indent=4, ensure_ascii=False)

    def run_ai_enhance_queue(self):
        self.bound_logger.debug(f'studio "{self.studio}": ai_queue: {self.get_ai_queue()}')

        for task in self.get_ai_queue():
            folder = task['folder_path']
            try:

                self.chown_folder(folder)
                self.index_folder(folder)

                self.bound_logger.debug(f'studio "{self.studio}": folder is: {folder}')
                action = self.get_folder_action(folder)
                self.bound_logger.debug(f'studio "{self.studio}": action: {action}')
                old_folder_name = folder.split("/")[-1]
                logger.debug(f'enhance_folder name: {old_folder_name}')

                new_folder_name = self.enhance_folder(folder, action)
                self.bound_logger.debug(f"new_folder_name: {new_folder_name}")
                new_folder = folder.replace(old_folder_name, new_folder_name)

                self.bound_logger.debug(f'studio "{self.studio}": NEW folder is: {new_folder}')
                folder_is_full = self.check_full_folder(new_folder)

                self.bound_logger.debug(f'studio "{self.studio}": folder {new_folder} is_full: {folder_is_full}')
                self.bound_logger.debug(f'studio "{self.studio}": new_folder: {new_folder}')

                self.bound_logger.debug(f'skip condition: {not (new_folder and folder_is_full)}')

                if not (new_folder and folder_is_full):
                    continue

                self.chown_folder(new_folder)
                self.index_folder(new_folder)
                self.remove_from_ai_queue(folder)
                self.remove_from_processed_folders(folder.split('/')[-1])

            except Exception as e:
                self.bound_logger.error(f'studio "{self.studio}": enhance folder {folder} error: {e}')

    def get_ready_folders_list(self):
        ready_folders = []

        hour_ranges = self.get_hour_ranges_from_processed_folders()

        self.bound_logger.debug(f'studio "{self.studio}": hour_ranges {hour_ranges}')

        for hour_range in hour_ranges:

            try:
                file_copier = FileCopier(self.config.get('path_settings'))
                current_month, current_date = file_copier.get_current_month_and_date()
                folder_path = file_copier.construct_paths(current_month, current_date, hour_range)
                if folder_path not in ready_folders:
                    ready_folders.append(folder_path)
            except Exception as e:
                self.bound_logger.error(f'studio "{self.studio}": Error constructing paths: {e}')

        return ready_folders

    @staticmethod
    def check_full_folder(folder_path):
        num_source_files = len([f for f in os.listdir(folder_path)
                                if os.path.isfile(os.path.join(folder_path, f))])
        num_enhanced_files = len([f for f in os.listdir(folder_path)
                                if os.path.isfile(os.path.join(folder_path, f))])
        if num_enhanced_files >= num_source_files:
            return True

    @staticmethod
    def chown_folder(folder_path):
        command = f'sudo chown -R www-data:www-data "{folder_path}"'
        os.system(command)

    @staticmethod
    def index_folder(folder_path: str):
        path = folder_path.replace('/cloud', '')
        command = f'sudo -u www-data php /var/www/cloud/occ files:scan -p "{path}" --shallow'
        os.system(command)

    def remove_from_processed_folders(self, hour_range):
        today_folders = self.get_hour_ranges_from_processed_folders()
        if hour_range in today_folders:
            today_folders.remove(hour_range)
            with open(f'processed_folders_{self.studio}.json', 'w') as f:
                json.dump(today_folders, fp=f, indent=4, ensure_ascii=False)

    def get_hour_ranges_from_processed_folders(self):
        try:
            with open(f'processed_folders_{self.studio}.json', 'r') as file:
                today_hour_ranges = self.filter_today_folders(json.load(file))
                return today_hour_ranges
        except Exception as e:
            self.bound_logger.error(f'studio "{self.studio}": Error get_hour_ranges_from_processed_folders: {e}')

    def filter_today_folders(self, hour_range_data):
        today_folders = []
        for hour_range in hour_range_data:
            start_hour = int(hour_range.split("-")[0])
            current_hour = datetime.now().hour
            if start_hour < current_hour:
                today_folders.append(hour_range)
        with open(f'processed_folders_{self.studio}.json', 'w') as file:
            json.dump(today_folders, fp=file, indent=4, ensure_ascii=False)
        return today_folders

    def remove_task_folder(self,folder):
        logger.debug(f"remove_task_folder folder: {folder}")
        command = f"echo {sudo_password} | sudo -S rm -fr '{folder}'"
        logger.info(command)

        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()

        logger.info(output)

        if process.returncode == 0:
            self.index_folder(os.path.dirname(folder))


def get_settings_files():
    settings_files = [os.path.join(os.getcwd(), 'portrait_config.ini'),
                      os.path.join(os.getcwd(), 'neo_config.ini'),
                      os.path.join(os.getcwd(), 'milan_config.ini')]
    return settings_files


def read_settings_file(settings_file):
    with open(settings_file, 'r', encoding='utf-8') as file:
        config = ConfigParser()
        config.read_file(file)
        path_settings = config['Settings']
        if config.has_section('ImageEnhancement'):
            enhance_settings = config['ImageEnhancement']
            return {'path_settings': path_settings, 'enhance_settings': enhance_settings}
        else:
            return {'path_settings': path_settings}


def run_enh_callers_for_host(host):
    bound_logger = logger.bind(host=host)

    while not stop_event.is_set():
        studios_settings_files = get_settings_files()
        for settings_file in studios_settings_files:
            settings = read_settings_file(settings_file)
            bound_logger.debug(f"studios_settings_files: {studios_settings_files}")
            bound_logger.debug(f"config {settings_file} try")
            if ((not settings.get('enhance_settings').get('action')) or
                    (host != settings['enhance_settings']['api_url'])):
                bound_logger.debug(f"studio {settings_file} check failed")
                continue

            enhance_caller = EnhanceCaller(settings=settings, ps_host=host, bound_logger=bound_logger)
            enhance_caller.run()

        time.sleep(10)


def send_folder_status_to_backend(
        cert_number, status,
        folder_path: str,
        completed=False,
        demo_task=False
):
    url = f"http://127.0.0.1:{str(backend_port)}/tasks/status/change"
    if completed:
        url = f"http://127.0.0.1:{str(backend_port)}/tasks/completed"
    body = {"cert_number": cert_number, "folder_path": folder_path}
    params = {"cert_number": cert_number, "status": status, "folder_path": folder_path}
    if demo_task:
        body['demo_task'] = 'true'
    try:
        if completed:
            response = requests.post(url, json=body)
        else:
            response = requests.patch(url, params=params)
        if response.status_code != 200:
            logger.error(f"Failed to send folder status to backend: {response.status_code}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")


def signal_handler(sig, frame):
    logger.debug(f'Signal {sig} received. Stopping threads...')
    stop_event.set()  # Signal threads to stop


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.add(f"general_enhance_caller.log",
               format="{time} {level} {extra[host]} {message}",
               rotation="1 MB",
               compression='zip',
               level="DEBUG")

    threads = []
    for host in enhancer_host_list:
        thread = threading.Thread(name=f"EnhancerThread-{host}", target=run_enh_callers_for_host, args=(host,))
        thread.start()
        threads.append(thread)

    try:
        for thread in threads:
            thread.join()
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
    finally:
        logger.debug("Cleaning up resources before exiting...")
        stop_event.set()
        for thread in threads:
            thread.join()
        logger.debug("All threads have completed. Exiting service.")


# def run_enhance_caller(settings, use_lock=False):
#     studio_name = settings.get('path_settings', {}).get('studio_name')
#
#     handler_id = logger.add(
#         f"{studio_name}_enhance_caller.log",
#         format="{time} {level} {message} host={extra[host]} studio={extra[studio_name]}",
#         rotation="1 MB",
#         compression='zip',
#         level="DEBUG"
#     )
#
#     if use_lock:
#         with exclusive_lock:
#             enhance_caller = EnhanceCaller(settings)
#             enhance_caller.run()
#     else:
#         enhance_caller = EnhanceCaller(settings)
#         enhance_caller.run()
#
#     logger.remove(handler_id)


# def forward_to_bot2(chat_id, message):
#     url = f"https://api.telegram.org/bot{BOT2_TOKEN}/sendMessage"
#     payload = {
#         "chat_id": chat_id,  # ID чата, куда отправить сообщение
#         "text": f"Received from Bot1: {message}"  # Текст сообщения
#     }
#     response = requests.post(url, json=payload)
#     return response.json()

# def handle_message(update: Update, context: CallbackContext):
#     chat_id = update.message.chat_id
#     message = update.message.text
#
#     # Обработка сообщения
#     update.message.reply_text(f"Бот 2 получил сообщение: {message}")