import os
import shutil
import subprocess
import sys
import time
import json
import pwd
import grp
import requests
import pytz
import setproctitle

from datetime import datetime, timedelta
from configparser import ConfigParser
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from loguru import logger

from nextcloud_ocs import NextcloudOCS
from tg_bot import TelegramBot
from yclients_api import YclientsService


class FileCopier:
    def __init__(self, config):
        self.destination_path = None
        self.config = config
        self.studio_timezone = pytz.timezone(config.get("TimeZoneName"))
        self.already_indexed_folders = []
        self.index_queue = []
        self.moved_file_path = None
        self.file_destination_hour_range = None
        self.all_files_moved = False
        self.nextcloud_ocs = NextcloudOCS()
        self.tg_bot = TelegramBot()
        try:
            self.yclients_service = YclientsService(config.get("Studio_name"))
        except:
            self.yclients_service = None
        self.shared_folders = []
        self.first_file_timestamp = {}

    def get_current_month_and_date(self):
        current_month_ru = datetime.now(self.studio_timezone).strftime('%B')
        current_month = self.translate_month_to_russian(current_month_ru)
        current_date = datetime.now(self.studio_timezone).strftime('%d.%m')
        return current_month, current_date

    def translate_month_to_russian(self, month_name):
        month_mapping = {
            'January': 'Январь',
            'February': 'Февраль',
            'March': 'Март',
            'April': 'Апрель',
            'May': 'Май',
            'June': 'Июнь',
            'July': 'Июль',
            'August': 'Август',
            'September': 'Сентябрь',
            'October': 'Октябрь',
            'November': 'Ноябрь',
            'December': 'Декабрь'
        }
        return month_mapping.get(month_name, month_name)

    def construct_paths(self, current_month, current_date, hour_range):
        base_path = os.path.join(
            self.config["BaseDirPath"],
            f'{current_month} {self.config["Studio_name"].upper()}',
            current_date,
            hour_range
        )
        return base_path

    def move_file(self, source_file, destination_path, month_path):
        filename = os.path.basename(source_file)
        destination_file = os.path.join(destination_path, filename)

        if not os.path.exists(destination_path):
            try:
                os.makedirs(destination_path, exist_ok=True)
                self.change_month_permissions(month_path)
            except Exception as e:
                logger.error(f"Error creating folder '{destination_path}': {e}")

        try:
            shutil.move(source_file, destination_file)
            logger.info(f'File {source_file} moved to {destination_path}')
            self.moved_file_path = destination_file
        except Exception as e:
            logger.error(f"Error moving file '{filename}' to '{destination_path}': {e}")
            self.moved_file_path = None

    def process_files(self, base_path):

        allowed_extension = self.config["FileExtension"].lower()

        unprocessed_files = False

        for filename in os.listdir(base_path):

            source_file = os.path.join(base_path, filename)

            if not (os.path.isfile(source_file)
                    and filename.lower().endswith(allowed_extension)):
                continue

            if not self.creation_date_check(source_file):
                continue

            if not self.transfer_active_check(source_file):
                self.destination_path = None
                self.moved_file_path = None
                self.file_destination_hour_range = None
                unprocessed_files = True
            else:

                self.file_destination_hour_range = self.get_hour_range_from_creation_time(source_file)

                if not self.file_destination_hour_range:
                    continue

                current_month, current_date = self.get_current_month_and_date()
                destination_path = self.construct_paths(current_month,
                                                        current_date,
                                                        self.file_destination_hour_range)
                month_path = os.path.join(self.config["BaseDirPath"],
                                          f'{current_month} {self.config["Studio_name"].upper()}')

                try:
                    if self.check_first_file_timestamp(destination_path, source_file):
                        self.move_file(source_file, destination_path, month_path)
                        self.destination_path = destination_path
                    else:
                        self.change_ownership(base_path)
                        self.run_index(base_path, skip_add_to_indexed=True)

                except Exception as e:
                    logger.error(e)

        if unprocessed_files:
            time.sleep(int(self.config["FileSizeCheckInterval"]))
            self.process_files(base_path)

        if self.destination_path:
            self.chown_files()

    def creation_date_check(self, source_file):
        try:
            creation_date = datetime.fromtimestamp(
                self.get_creation_time(source_file),
                self.studio_timezone).strftime('%d.%m')
            current_date = self.get_current_month_and_date()[1]

            if creation_date == current_date:
                return True
            else:
                logger.debug((f'source_file: {source_file} / creation_date: {creation_date}, '
                              f'current_date: {current_date}'))
        except Exception as e:
            logger.error(f'Error getting creation date: {e}')

    def transfer_active_check(self, source_file):
        initial_size = os.path.getsize(source_file)
        time.sleep(int(self.config["FileSizeCheckInterval"]))
        try:
            current_size = os.path.getsize(source_file)

            if initial_size == current_size:
                return True
        except Exception as e:
            logger.error(f'transfer_active_check: {e}; source file: {source_file}')

    def chown_files(self):
        path = self.destination_path
        subprocess.run(['sudo', 'chown', '-R', 'www-data:www-data', path])

    def run(self):
        studio_root_path = self.config["BaseDirPath"]
        root_path_message = f'studio root path: {studio_root_path}'

        if not os.path.exists(studio_root_path):
            root_path_message = f'{root_path_message} does_not_exist'
            logger.info(root_path_message)
            return

        logger.info(root_path_message)

        while True:
            self.update_processed_folders()  # If outdated also clears the self.shared_folders

            self.delete_outdated_folders()

            self.process_files(studio_root_path)

            if self.destination_path:
                time.sleep(4)
                try:
                    self.change_ownership(self.destination_path)
                except Exception as e:
                    logger.error(e)
                self.check_if_all_files_moved(studio_root_path)

                if self.all_files_moved and self.destination_path not in self.already_indexed_folders:
                    self.add_to_index_queue(self.destination_path)
                    self.all_files_moved = False

            self.run_index_queue(studio_root_path)

            time.sleep(int(self.config["IterationSleepTime"]))

    def delete_outdated_folders(self):
        current_date = datetime.now(self.studio_timezone).strftime('%d')
        if self.config['Delete_outdated_folders'] != 'Yes' or current_date != '20':
            return

        now = datetime.now(self.studio_timezone)
        studio_name = self.config["Studio_name"]
        studio_base_path = self.config["BaseDirPath"]
        current_month = self.translate_month_to_russian(now.strftime("%B"))

        for folder_name in os.listdir(studio_base_path):
            folder_path = os.path.join(studio_base_path, folder_name)
            if os.path.isdir(folder_path):
                if current_month not in folder_name and studio_name.upper() in folder_name:
                    suffix = f'{studio_name}/{current_month} {studio_name.upper()}'
                    logger.info(f'deleting folder {suffix}')
                    self.move_folder_to_trash_bin(suffix)

    def move_folder_to_trash_bin(self, suffix):

        load_dotenv()
        username = os.environ.get('NEXTCLOUD_USERNAME')
        password = os.environ.get('NEXTCLOUD_PASSWORD')

        server_url = 'https://cloud.reflect-studio.ru'

        file_path = f'/remote.php/dav/files/reflect/{suffix}'

        try:
            response = requests.delete(f'{server_url}{file_path}', auth=HTTPBasicAuth(username, password))

            if response.status_code == 204:
                logger.info(f'Folder {suffix} moved to trash bin')
            else:
                print(f'Failed to move file to trash bin. Status code: {response.status_code}')
        except Exception as e:
            logger.error(f'Move to trash bin error: {e}')


    def check_folder_exists_console(self, path):
        command = f"ls {path}"
        exit_status = os.system(command)
        if exit_status == 0:
            return True
        else:
            return False

    def check_first_file_timestamp(self, destination_path, source_file):

        delay_time = int(config.get("FirstFileDelayTime")) if config.get("FirstFileDelayTime") else 10

        if not os.path.exists(destination_path):
            source_file_creation_time = self.get_creation_time(source_file)

            if destination_path not in self.first_file_timestamp:
                self.first_file_timestamp[destination_path] = source_file_creation_time
            else:
                current_time = datetime.now().astimezone(self.studio_timezone)
                delta = current_time - datetime.fromtimestamp(source_file_creation_time, self.studio_timezone)
                if delta > timedelta(minutes=delay_time):
                    del self.first_file_timestamp[destination_path]
                    return True
        else:
            return True

    def check_if_all_files_moved(self, base_path):

        if not (self.moved_file_path and self.file_destination_hour_range):
            return
        if self.destination_path in self.already_indexed_folders:
            return

        source_files = [f for f in os.listdir(base_path) if os.path.isfile(os.path.join(base_path, f))
                        and f.lower().endswith('.jpg')]

        same_hour_range = next((source_file for source_file in source_files if
                              self.get_hour_range_from_creation_time(
                                  os.path.join(base_path, source_file))
                                == self.file_destination_hour_range),
                             None)

        if not same_hour_range:
            self.all_files_moved = True

    def run_index(self, destination_subdir, skip_add_to_indexed=False):
        setproctitle.setproctitle("copy_script_run_index")

        full_dest_subdir = destination_subdir
        destination_subdir = destination_subdir.replace('/cloud', '')
        formatted_dest_subdir = self.modify_path_for_index(destination_subdir)

        command = f'sudo -u www-data php /var/www/cloud/occ files:scan -p {formatted_dest_subdir} --shallow'

        try:
            process = subprocess.run(
                command,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            if process.returncode == 0:
                if not skip_add_to_indexed:
                    self.already_indexed_folders.append(full_dest_subdir)
                if full_dest_subdir in self.index_queue:
                    self.remove_from_index_queue(full_dest_subdir)
                self.save_processed_folders()
            else:
                logger.error(f"Error executing command: {command}, stderr: {process.stderr.decode()}")

            logger.info(f"Console output: {process.stdout.decode()}")

        except Exception as e:
            logger.error(f"Error executing command: {command}, {e}")

    def run_index_queue(self, studio_root_path):
        for path in self.index_queue:
            if path in self.already_indexed_folders or not self.check_queue_hour_range(path):
                continue
            self.change_ownership(path)
            self.run_index(path)
            self.run_index(studio_root_path, skip_add_to_indexed=True)
            if self.first_file_timestamp:
                logger.debug(f'first file created: {str(self.first_file_timestamp)}')
            try:
                self.generate_and_store_share_folder_url(path)
            except Exception as e:
                logger.error(f'generate_and_store_share_folder_url: {e}')

    def generate_and_store_share_folder_url(self, path):
        path_for_share = self.modify_path_for_share_folder(path)
        self.get_folder_url(path_for_share)
        if self.nextcloud_ocs.shared_folder_url:
            folder_hour_range = path_for_share.split("/")[-1]
            self.yclients_service.get_appointed_client_info(
                folder_hour_range=folder_hour_range)
            if self.yclients_service.client_info:
                self.save_shared_folder()

    def modify_path_for_index(self, destination_subdir):
        # destination_subdir = destination_subdir.replace('/cloud', '')
        # studio = self.config["Studio_name"]
        # parts = destination_subdir.split(studio)
        #
        # second_part = parts[1]
        # month_studio_part = second_part.split("/")[1]
        # month_studio_part_quoted = f'"{month_studio_part}"'
        # new_second_part = second_part.replace(month_studio_part, month_studio_part_quoted)
        # return parts[0] + studio + new_second_part

        # destination_subdir = destination_subdir.replace('/cloud', '')
        folders = destination_subdir.split(os.path.sep)
        wrapped_folders = ['"' + folder + '"' if folder else '' for folder in folders]
        wrapped_path = os.path.sep.join(wrapped_folders)

        return wrapped_path

    def modify_path_for_exist_check(self, path):
        # Quote each part of the path and join them back together
        quoted_parts = [f'"{part}"' for part in path.split('/') if part]
        formatted_path = '/'.join(quoted_parts)

        # Return the formatted path as a raw string literal
        return f'r"{formatted_path}"'

    @staticmethod
    def modify_path_for_share_folder(path):
        new_path = path.split('/files/')[1]
        return new_path

    def get_hour_range_from_creation_time(self, file_path):
        try:
            creation_time = self.get_creation_time(file_path)
            creation_datetime = datetime.fromtimestamp(creation_time, self.studio_timezone)
            hour_range = f"{creation_datetime.hour}-{creation_datetime.hour + 1}"
            return hour_range
        except Exception as e:
            logger.error(f"Error retrieving creation time for '{file_path}': {e}")
            return None

    def get_current_hour_range(self):
        current_hour = datetime.now(self.studio_timezone).hour
        return f"{current_hour}-{current_hour + 1}"

    def check_queue_hour_range(self, path):
        current_hour_range = self.get_current_hour_range()
        hour_range = path.split('/')[-1]
        if current_hour_range != hour_range:
            return True

    @staticmethod
    def get_creation_time(file_path):
        try:
            mod_command = ['stat', '-c', '%Y', file_path]
            mod_result = subprocess.run(mod_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                        check=True)
            modification_time_stat = float(mod_result.stdout.strip())

            create_command = ['stat', '-c', '%W', file_path]
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

    @staticmethod
    def change_ownership(directory_path, user='www-data', group='www-data'):
        try:
            uid = pwd.getpwnam(user).pw_uid
            gid = grp.getgrnam(group).gr_gid

            while directory_path != '/':
                os.chown(directory_path, uid, gid)
                directory_path = os.path.dirname(directory_path)

        except Exception as e:
            logger.error(f"Error changing ownership of '{directory_path}' and its parent directories: {e}")

    @staticmethod
    def change_month_permissions(month_path):
        command = f'sudo chmod -R g+w "{month_path}"'
        os.system(command)

    def get_folder_url(self, folder):
        self.nextcloud_ocs.get_token()
        if self.nextcloud_ocs.csrf_token:
            self.nextcloud_ocs.send_request_folder_share(folder)
        if self.nextcloud_ocs.error:
            logger.error(f'Error getting url: {self.nextcloud_ocs.error}')
            return
        if self.nextcloud_ocs.response:
            self.nextcloud_ocs.get_url_from_response()

        if not self.nextcloud_ocs.shared_folder_url:
            logger.error(f'No shared_folder_url received: {self.nextcloud_ocs.error}')
            return

    def add_to_index_queue(self, path):
        if path not in self.index_queue:
            self.index_queue.append(path)
            self.save_processed_folders()

    def remove_from_index_queue(self, path):
        self.index_queue.remove(path)
        self.save_processed_folders()

    def update_processed_folders(self):
        current_date = datetime.now(self.studio_timezone).strftime('%d.%m')
        processed_data = self.load_processed_folders()
        process_date = processed_data.get('process_date')
        already_indexed_folders = processed_data.get('already_indexed')
        index_queue = processed_data.get('index_queue')

        if process_date:
            if process_date == current_date:
                self.already_indexed_folders = already_indexed_folders
                self.index_queue = index_queue
            else:
                self.shared_folders = []
                logger.debug(f"self.index_queue: {self.index_queue}")
                logger.debug(f"self.already_indexed_folders: {self.already_indexed_folders}")
                self.clear_processed_folders()
        else:
            logger.debug(f"no process_date received: {current_date}")
            logger.debug(f"self.index_queue: {self.index_queue}")
            logger.debug(f"self.already_indexed_folders: {self.already_indexed_folders}")

    def load_processed_folders(self):
        filename = f'processed_folders_{config.get("Studio_name")}.json'
        if not os.path.isfile(filename):
            self.save_processed_folders()
            return {'process_date': None, 'already_indexed': [], 'index_queue': []}
        try:
            with open(filename, 'r') as file:
                return json.load(file)
        except Exception as e:
            logger.error(f"Error loading processed folders: {e}")
            return {'process_date': None, 'already_indexed': [], 'index_queue': []}

    def save_processed_folders(self):
        current_date = datetime.now(self.studio_timezone).strftime('%d.%m')

        data = {
            'process_date': current_date,
            'already_indexed': list(self.already_indexed_folders),
            'index_queue': list(self.index_queue)
        }

        with open(f'processed_folders_{config.get("Studio_name")}.json', 'w') as file:
            json.dump(data, file)

    @staticmethod
    def clear_processed_folders():
        with open(f'processed_folders_{config.get("Studio_name")}.json', 'w') as json_file:
            json.dump({}, json_file)

    def save_shared_folder(self):

        filename = f'/cloud/reflect/files/Рассылка/{studio_name}_рассылка.json'

        if os.path.isfile(filename):
            self.shared_folders = self.get_shared_folders(filename)

        new_shared_folder = {
            "client_name": self.yclients_service.client_info['client_name'],
            "folder_url": self.nextcloud_ocs.shared_folder_url,
            "client_id": self.yclients_service.client_info['client_id'],
            "client_phone_number": self.yclients_service.client_info['client_phone_number'],
            "client_email": self.yclients_service.client_info.get('client_email', "")

        }

        self.shared_folders.append(new_shared_folder)
        self.update_shared_folders_file(filename)
        self.change_ownership(filename)
        self.run_index('/cloud/reflect/files/Рассылка/',
                       skip_add_to_indexed=True)

    @staticmethod
    def get_shared_folders(filename):
        with open(filename, 'r', encoding='utf-8') as file:
            return json.load(file)['shared_folders']

    def update_shared_folders_file(self, filename):
        current_date = datetime.now(self.studio_timezone).strftime('%d.%m.%Y')
        shared_folders_data = {
            'date': current_date,
            'shared_folders': self.shared_folders
        }
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(shared_folders_data, file, indent=4)


def read_config(config_file):
        with open(config_file, 'r', encoding='utf-8') as file:
            config = ConfigParser()
            config.read_file(file)
        return config['Settings']


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python photos_copy_script.py <studio_config_file>")
        sys.exit(1)

    studio_config_file = sys.argv[1]
    config = read_config(studio_config_file)

    try:
        studio_name = config.get("Studio_name")
    except Exception as e:
        logger.error(f'error reading config: {e}')
    log_file_name = config.get("LogFile")

    logger.add(log_file_name,
               format="{time} {level} {message}",
               rotation="10 MB",
               compression='zip',
               level="INFO")

    studio_path = config.get("BaseDirPath")
    logger.info(f'BaseDirPath: {studio_path}')

    file_copier = FileCopier(config)
    file_copier.run()
