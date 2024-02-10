import os
import shutil
import subprocess
import sys
import time
import asyncio
import json
import pwd
import grp

from datetime import datetime
from configparser import ConfigParser

import pytz
import setproctitle

from loguru import logger


class FileCopier:
    def __init__(self, config):
        self.destination_path = None
        self.config = config
        self.timezone_moscow = pytz.timezone('Europe/Moscow')  # Set Moscow timezone
        self.already_indexed_folders = []
        self.index_queue = []
        self.moved_file_path = None
        self.file_destination_hour_range = None
        self.all_files_moved = False

    def get_current_month_and_date(self):
        current_month_ru = datetime.now(self.timezone_moscow).strftime('%B')
        current_month = self.translate_month_to_russian(current_month_ru)
        current_date = datetime.now(self.timezone_moscow).strftime('%d.%m')
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
        logger.info(f'base_path for {self.config["Studio_name"]}: {base_path}')
        return base_path

    def move_file(self, source_file, destination_path):
        filename = os.path.basename(source_file)
        destination_file = os.path.join(destination_path, filename)

        if not os.path.exists(destination_file):
            try:
                os.makedirs(destination_path, exist_ok=True)
                logger.info(f'File {source_file} moved to {destination_path}')
                shutil.move(source_file, destination_file)
                self.moved_file_path = destination_file
            except Exception as e:
                logger.error(f"Error moving file '{filename}' to '{destination_path}': {e}")
                self.moved_file_path = None

    def process_files(self, base_path):

        allowed_extension = self.config["FileExtension"].lower()

        for filename in os.listdir(base_path):

            source_file = os.path.join(base_path, filename)

            if not (os.path.isfile(source_file) and filename.lower().endswith(allowed_extension)):
                continue  # Skip files that don't have the allowed extension

            creation_date = datetime.fromtimestamp(os.path.getctime(source_file), self.timezone_moscow).strftime(
                '%d.%m')
            current_date = self.get_current_month_and_date()[1]

            logger.info(f"Processing file '{source_file}'")
            logger.info(f"Creation date: {creation_date}")
            logger.info(f"Current date: {current_date}")

            if creation_date != current_date:
                continue

            # Process only files with the allowed extension at the source folder level
            initial_size = os.path.getsize(source_file)
            time.sleep(int(self.config["FileSizeCheckInterval"]))
            try:
                current_size = os.path.getsize(source_file)

                if initial_size == current_size:
                    self.file_destination_hour_range = self.get_hour_range_from_creation_time(source_file)

                    if not self.file_destination_hour_range:
                        logger.warning(f"Skipped file '{filename}' due to invalid creation time.")
                        continue

                    current_month, current_date = self.get_current_month_and_date()
                    destination_path = self.construct_paths(current_month,
                                                            current_date,
                                                            self.file_destination_hour_range)

                    self.move_file(source_file, destination_path)
                    self.destination_path = destination_path
                else:
                    self.destination_path = None
                    self.moved_file_path = None
                    self.file_destination_hour_range = None
                    logger.warning(f"File '{filename}' is still being written. Skipping.")

            except Exception as error_msg:
                logger.error(f"can't get file size for file '{filename}': {error_msg}")
                continue

    def run(self):
        while True:
            self.update_processed_folders()

            studio_root_path = self.config["BaseDirPath"]

            logger.info(f'studio root path: {studio_root_path}')

            if not self.check_folder_exists_os_path(studio_root_path):
                logger.info(f'studio root path {studio_root_path} does_not_exist')
                time.sleep(int(self.config["IterationSleepTime"]))
                continue

            self.process_files(studio_root_path)

            logger.info(f'self.destination_path: {self.destination_path}')

            if self.destination_path:
                self.check_if_all_files_moved(studio_root_path)

                if self.all_files_moved:
                    self.add_to_index_queue(self.destination_path)

            self.run_index_queue()

            time.sleep(int(self.config["IterationSleepTime"]))

    def check_folder_exists_console(self, path):
        command = f"ls {path}"
        logger.info(f'command: {command}')
        exit_status = os.system(command)
        logger.info(f'exit_status: {exit_status}')
        if exit_status == 0:
            return True
        else:
            return False

    def check_folder_exists_os_path(self, path):
        if os.path.exists(path):
            return True

    def check_if_all_files_moved(self, base_path):
        logger.info(f'base path: {base_path}')
        logger.info(f'self.moved_file_path: {self.moved_file_path}, '
                    f'self.file_destination_hour_range: {self.file_destination_hour_range}')
        if not (self.moved_file_path and self.file_destination_hour_range):
            logger.info(f"no parameters for this file")
            return
        if self.destination_path in self.already_indexed_folders:
            logger.info(f"{self.destination_path} exists in already_indexed_folders")
            return

        source_files = [f for f in os.listdir(base_path) if os.path.isfile(os.path.join(base_path, f))
                        and f.lower().endswith('.jpg')]

        logger.info(f'source_files: {source_files}')

        same_hour_range = next((source_file for source_file in source_files if
                              self.get_hour_range_from_creation_time(
                                  os.path.join(base_path, source_file))
                                == self.file_destination_hour_range),
                             None)

        logger.info(f'same_hour_range: {same_hour_range}')

        if not same_hour_range:
            self.all_files_moved = True

    def run_index(self, destination_subdir):
        setproctitle.setproctitle("copy_script_run_index")

        destination_subdir = destination_subdir.replace('/cloud', '')

        formatted_dest_subdir = self.modify_path_for_index(destination_subdir)

        command = f'sudo -u www-data php /var/www/cloud/occ files:scan -p {formatted_dest_subdir}'

        logger.info(f"command: {command}")

        try:
            process = subprocess.run(
                command,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            if process.returncode == 0:
                logger.info(f"Command executed successfully: {command}")
                self.already_indexed_folders.append(destination_subdir)
                self.remove_from_index_queue(destination_subdir)
                self.save_processed_folders()
            else:
                logger.error(f"Error executing command: {command}, stderr: {process.stderr.decode()}")

            logger.info(f"Console output: {process.stdout.decode()}")

        except Exception as e:
            logger.error(f"Error executing command: {command}, {e}")

    def run_index_queue(self):
        for path in self.index_queue:
            if path in self.already_indexed_folders or not self.check_queue_hour_range(path):
                continue
            self.change_ownership(path)
            self.run_index(path)

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

    def get_hour_range_from_creation_time(self, file_path):
        try:
            creation_time = os.path.getctime(file_path)
            creation_datetime = datetime.fromtimestamp(creation_time, self.timezone_moscow)
            hour_range = f"{creation_datetime.hour}-{creation_datetime.hour + 1}"
            return hour_range
        except Exception as e:
            logger.error(f"Error retrieving creation time for '{file_path}': {e}")
            return None

    def get_current_hour_range(self):
        current_hour = datetime.now(self.timezone_moscow).hour
        return f"{current_hour}-{current_hour + 1}"

    def check_queue_hour_range(self, path):
        current_hour_range = self.get_current_hour_range()
        hour_range = path.split('/')[-1]
        if current_hour_range != hour_range:
            return True
        else:
            logger.info('file created this hour')

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

    def add_to_index_queue(self, path):
        if path not in self.index_queue:
            self.index_queue.append(path)
            self.save_processed_folders()

    def remove_from_index_queue(self, path):
        self.index_queue.remove(path)
        self.save_processed_folders()

    def update_processed_folders(self):
        current_date = datetime.now(self.timezone_moscow).strftime('%d.%m')
        processed_data = self.load_processed_folders()
        process_date = processed_data.get('process_date')
        already_indexed_folders = processed_data.get('already_indexed')

        if process_date:
            self.already_indexed_folders = already_indexed_folders

            if process_date == current_date:
                self.already_indexed_folders = already_indexed_folders
            else:
                self.clear_processed_folders()

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
        current_date = datetime.now(self.timezone_moscow).strftime('%d.%m')

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
        print(e)
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
