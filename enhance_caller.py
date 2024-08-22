import os
import json
import time

import pytz
import requests

from configparser import ConfigParser
from loguru import logger

from photos_copy_script import FileCopier, read_config


class EnhanceCaller:

    def __init__(self, settings, base_path=None):
        self.studio = settings['path_settings']['Studio_name']
        self.photos_path = settings['path_settings']['BaseDirPath']
        self.files_extension = settings['path_settings']['FileExtension']
        self.studio_timezone = pytz.timezone(settings['path_settings']['TimeZoneName'])
        self.api_url = settings['enhance_settings']['api_url']
        self.action = settings['enhance_settings']['action']
        self.base_path = base_path or os.getcwd()

    def run(self):

        if not os.path.exists(self.photos_path):
            logger.error(f'Folder {self.photos_path} does not exist')
            return
        today_folders = self.get_ready_folders_list()
        if not today_folders:
            return

        self.index_ready_folders(today_folders)

        for folder in today_folders:
            self.add_to_ai_queue(folder)

        self.run_ai_enhance_queue()

    def index_ready_folders(self, ready_folders):
        for folder in ready_folders:
            try:
                self.index_folder(folder)
            except Exception as e:
                logger.error(f'Error indexing folder {folder}: {e}')

    def enhance_folder(self, folder, action):

        enhance_folder_url = self.api_url + "/enhance_folder/"

        data = {
            "studio_name": folder.split('/')[-4],
            "action_name": action,
            "month": folder.split('/')[-3],
            "day": folder.split('/')[-2],
            "hour": folder.split('/')[-1],
        }

        logger.info(f'data: {data}')

        response = requests.post(enhance_folder_url, json=data)

        if response.status_code != 200:
            if 'already exists' not in response.json().get('error_message'):
                logger.error(f"Error occurred: {response.json().get('error_message')}")

        elif response.json().get('error'):
            logger.error(f"Error occurred: {response.json().get('error_message')}")

        else:
            self.remove_from_processed_folders(folder)
            return f'{folder}_AI'

    def get_folder_action(self, folder):

        if folder.split('/')[-4] == self.studio:
            return self.action

        config_file_mapping = {
            'Силуэт': 'silhouette_config.ini',
            'Отражение': 'reflect_config.ini',
            'Reflect KZ': 'kz_config.ini'
        }

        folder_config_file = config_file_mapping[folder.split('/')[-4]]

        action = read_settings_file(
            os.path.join(os.getcwd(), folder_config_file))['enhance_settings'].get('action')

        return action

    def add_to_ai_queue(self, folder):
        ai_index_queue = self.get_ai_queue()
        if folder in ai_index_queue:
            return
        ai_index_queue.append(folder)
        with open(os.path.join(self.base_path, 'ai_enhance_queue.json'), 'w') as f:
            json.dump(ai_index_queue, f)

    def get_ai_queue(self):
        if not os.path.exists(os.path.join(self.base_path, 'ai_enhance_queue.json')):
            with open(os.path.join(self.base_path, 'ai_enhance_queue.json'), 'w') as f:
                json.dump([], f)
                return []
        with open(os.path.join(self.base_path, 'ai_enhance_queue.json'), 'r') as f:
            return json.load(f)

    def remove_from_ai_queue(self, folder):
        ai_index_queue = self.get_ai_queue()
        if folder in ai_index_queue:
            ai_index_queue.remove(folder)
            with open(os.path.join(self.base_path, 'ai_enhance_queue.json'), 'w') as f:
                json.dump(ai_index_queue, f)

    def run_ai_enhance_queue(self):
        logger.info(f'ai_queue: {self.get_ai_queue()}')

        for folder in self.get_ai_queue():
            try:
                logger.info(f'folder is: {folder}')
                action = self.get_folder_action(folder)
                new_folder = self.enhance_folder(folder, action)
                logger.info(f'NEW folder is: {new_folder}')

                if new_folder:
                    self.chown_folder(new_folder)
                    self.index_folder(new_folder)
                    self.remove_from_ai_queue(folder)
            except Exception as e:
                logger.error(f'enhance folder {folder} error: {e}')

    def get_ready_folders_list(self):
        ready_folders = []

        hour_ranges = self.get_hour_ranges_from_processed_folders()

        for hour_range in hour_ranges:

            try:
                config = read_config(settings_file)
                file_copier = FileCopier(config)
                current_month, current_date = file_copier.get_current_month_and_date()
                folder_path = file_copier.construct_paths(current_month, current_date, hour_range)
                logger.debug(f'folder path: {folder_path}')
                if folder_path not in ready_folders:
                    ready_folders.append(folder_path)
            except Exception as e:
                logger.error(f'Error constructing paths: {e}')

        return ready_folders

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
        today_folders.remove(hour_range)
        with open(f'processed_folders_{self.studio}.json', 'w') as f:
            json.dump(today_folders, f)

    def get_hour_ranges_from_processed_folders(self):
        try:
            with open(f'processed_folders_{self.studio}.json', 'r') as file:
                data = json.load(file)
                return data
        except Exception as e:
            logger.error(f'Error get_hour_ranges_from_processed_folders: {e}')


def get_settings_files():
    settings_files = [os.path.join(os.getcwd(), 'portrait_config.ini')]
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


if __name__ == '__main__':
    while True:
        studios_settings_files = get_settings_files()
        for settings_file in studios_settings_files:
            settings = read_settings_file(settings_file)
            if settings.get('enhance_settings').get('action'):
                studio_name = settings.get('path_settings').get('studio_name')

                handler_id = logger.add(f"{studio_name}enhance_caller.log",
                           format="{time} {level} {message}",
                           rotation="1 MB",
                           compression='zip',
                           level="DEBUG")

                enhance_caller = EnhanceCaller(settings)
                enhance_caller.run()
                logger.remove(handler_id)
        time.sleep(10)
