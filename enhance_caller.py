import os
import json
import signal
import time
import pytz
import requests
import threading

from configparser import ConfigParser
from loguru import logger
from datetime import datetime

from photos_copy_script import FileCopier, read_config

exclusive_lock = threading.Lock()
stop_event = threading.Event()
enhancer_host_list = [
    'http://192.168.0.178:8000',
    'http://192.168.0.199:8000'
]

config_file_mapping = {
                'Силуэт': 'silhouette_config.ini',
                'Отражение': 'reflect_config.ini',
                'Reflect KZ': 'kz_config.ini',
                'Neo': 'neo_config.ini',
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

        if not os.path.exists(folder):
            return

        enhance_folder_url = self.api_url + "/enhance_folder/"

        data = {
            "studio_name": folder.split('/')[-4],
            "action_name": action,
            "month": folder.split('/')[-3],
            "day": folder.split('/')[-2],
            "hour": folder.split('/')[-1],
        }

        if "_demo" in data["hour"]:
            data["hour"] = data["hour"].replace("_demo", "")

        self.bound_logger.debug(f'studio "{self.studio}": data: {data}')

        response = requests.post(enhance_folder_url, json=data)

        if response.status_code != 200:
            if 'already exists' not in response.json().get('error_message'):
                self.bound_logger.error(f"studio {self.studio}: Error occurred: {response.json().get('error_message')}")

        elif response.json().get('error'):
            self.bound_logger.error(f"studio {self.studio}: Error occurred: {response.json().get('error_message')}")

        else:
            result_folder_name = response.json().get('folder_path')
            if "_demo" in data["hour"]:
                if "_AI" in result_folder_name:
                    result_folder_name = result_folder_name.replace("_AI", "_demo_AI")
                elif "_BW" in result_folder_name:
                    result_folder_name = result_folder_name.replace("_BW", "_demo_BW")
            self.remove_from_processed_folders(folder)
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
                new_folder = self.enhance_folder(folder, action)
                self.bound_logger.debug(f'studio "{self.studio}": NEW folder is: {new_folder}')
                folder_is_full = self.check_full_folder(new_folder)

                self.bound_logger.debug(f'studio "{self.studio}": folder {folder} is_full: {folder_is_full}')
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

            # handler_id = logger.add(f"general_enhance_caller.log",
            #                         format="{time} {level} {message} host={extra[host]} studio={extra[studio_name]}",
            #                         rotation="1 MB",
            #                         compression='zip',
            #                         level="DEBUG")

            enhance_caller = EnhanceCaller(settings=settings, ps_host=host, bound_logger=bound_logger)
            enhance_caller.run()
            # bound_logger.remove(handler_id)

        time.sleep(10)


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

