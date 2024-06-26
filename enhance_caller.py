import os
import re
import json
import subprocess
import pytz
import requests

from configparser import ConfigParser
from loguru import logger
from datetime import datetime, date

from lockfile import write_to_common_file


class EnhanceCaller:

    def __init__(self, settings):
        self.studio = settings['path_settings']['Studio_name']
        self.photos_path = settings['path_settings']['BaseDirPath']
        self.files_extension = settings['path_settings']['FileExtension']
        self.studio_timezone = pytz.timezone(settings['path_settings']['TimeZoneName'])
        self.api_url = settings['ImageEnhancement']['api_url']
        self.action = settings['ImageEnhancement']['action']

    def run(self):

        today_folders = self.get_folders_modified_today()

        try:
            for folder in today_folders:
                if self.check_not_enhanced_yet(folder):
                    if self.check_folder_not_in_process(folder):
                        new_folder = self.enhance_folder(folder)
                        if new_folder:
                            self.chown_folder(new_folder)
                            self.index_folder(new_folder)
        except Exception as e:
            logger.error(e)

    def enhance_folder(self, folder):

        enhance_folder_url = self.api_url + "enhance_folder/"

        data = {
            "studio_name": self.studio,
            "action_name": self.action,
            "month": folder.split('/')[-3],
            "day": folder.split('/')[-2],
            "hour": folder.split('/')[-1],
        }

        response = requests.post(enhance_folder_url, json=data)

        if response.status_code != 200:
            logger.error(f"Error occurred: {response.json().get('error_message')}")
        elif response.json().get('status') == 'success':
            self.save_enhanced_folders(folder)
            return f'{folder}_RS'

    def get_folders_modified_today(self):
        today = date.today()

        folders_modified_today = []
        for root, dirs, files in os.walk(self.photos_path):
            for dir_name in dirs:
                if re.match(r'^\d{1,2}-\d{1,2}$', dir_name):
                    dir_path = os.path.join(root, dir_name)
                    folder_creation_day = date.fromtimestamp(self.get_creation_time(dir_path))
                    if folder_creation_day == today:
                        folders_modified_today.append(dir_path)

        return folders_modified_today

    def check_folder_not_in_process(self, folder):
        already_indexed_list = self.gather_already_indexed()
        if folder in already_indexed_list:
            return True
        else:
            logger.debug(f'folder: {folder} is not indexed yet')

    @staticmethod
    def gather_already_indexed():
        current_directory = os.getcwd()
        already_indexed_list = []
        for filename in os.listdir(current_directory):
            if filename.startswith("processed_folders_"):
                with open(os.path.join(current_directory, filename), 'r') as file:
                    data = json.load(file)
                    already_indexed_list.extend(data.get('already_indexed', []))
        return already_indexed_list

    @staticmethod
    def chown_folder(folder_path):
        command = f'sudo chown -R www-data:www-data "{folder_path}"'
        os.system(command)

    @staticmethod
    def index_folder(folder_path: str):
        path = folder_path.replace('/cloud', '')
        command = f'sudo -u www-data php /var/www/cloud/occ files:scan -p "{path}" --shallow'
        os.system(command)

    @staticmethod
    def get_creation_time(dir_path):
        try:
            mod_command = ['stat', '-c', '%Y', dir_path]
            mod_result = subprocess.run(mod_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                        check=True)
            modification_time_stat = float(mod_result.stdout.strip())

            create_command = ['stat', '-c', '%W', dir_path]
            create_result = subprocess.run(create_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                           check=True)
            creation_time_stat = float(create_result.stdout.strip())

            if modification_time_stat < creation_time_stat:
                return modification_time_stat
            else:
                return creation_time_stat
        except subprocess.CalledProcessError as e:
            logger.error(f"Error get_creation_time: {e}")
            return None

    def check_not_enhanced_yet(self, folder):
        enhanced_folders = self.load_enhanced_folders().get('enhanced_folders', [])
        return folder not in enhanced_folders

    @staticmethod
    def load_enhanced_folders():
        try:
            with open('enhanced_folders.json', 'r') as file:
                data = json.load(file)
                return data
        except FileNotFoundError:
            return {'date': None, 'enhanced_folders': []}

    def save_enhanced_folders(self, enhanced_folder):
        current_date = datetime.now(self.studio_timezone).strftime('%d.%m')
        enhanced_folders = self.load_enhanced_folders().get('enhanced_folders') or []
        enhanced_folders.append(enhanced_folder)

        data = {
            'date': current_date,
            'enhanced_folders': list(enhanced_folders),
        }

        write_to_common_file(data, 'enhanced_folders.json')


def get_settings_files():
    settings_files = [os.path.join(os.getcwd(), file) for file
                      in os.listdir(os.getcwd()) if file.endswith('_config.ini')]
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
            if settings.get('action'):
                studio_name = settings.get('path_settings').get('studio_name')

                logger.add(f"{studio_name}_image_enhancer.log",
                           format="{time} {level} {message}",
                           rotation="1 MB",
                           compression='zip',
                           level="DEBUG")

                enhance_caller = EnhanceCaller(settings)
                enhance_caller.run()
