import os
import shutil
import time
import asyncio

from datetime import datetime
from configparser import ConfigParser

import pytz
import setproctitle

from loguru import logger


class FileCopier:
    def __init__(self, config):
        self.config = config
        self.timezone_moscow = pytz.timezone('Europe/Moscow')  # Set Moscow timezone
        self.processed_folders = set()  # Set to store processed folders

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

    def construct_paths(self, current_month, current_date):
        base_path = os.path.join(
            self.config["BaseDirPath"],
            self.config["Studio_name"],
            f'{current_month} {self.config["Studio_name"].upper()}',
            current_date
        )
        return base_path

    def copy_files(self, base_path):
        allowed_extension = self.config["FileExtension"].lower()

        for filename in os.listdir(base_path):
            source_file = os.path.join(base_path, filename)

            if not (os.path.isfile(source_file) and filename.lower().endswith(allowed_extension)):
                continue  # Skip files that don't have the allowed extension

            # Process only files with the allowed extension at the source folder level
            initial_size = os.path.getsize(source_file)
            time.sleep(int(self.config["FileSizeCheckInterval"]))
            current_size = os.path.getsize(source_file)

            if initial_size == current_size:
                destination_hour_range = self.get_hour_range_from_creation_time(source_file)

                if not destination_hour_range:
                    logger.warning(f"Skipped file '{filename}' due to invalid creation time.")
                    continue

                destination_subdir = os.path.join(base_path, destination_hour_range)
                os.makedirs(destination_subdir, exist_ok=True)

                destination_file = os.path.join(destination_subdir, filename)

                if not os.path.exists(destination_file):
                    shutil.copy2(source_file, destination_file)
                    logger.info(f"File '{filename}' copied to '{destination_subdir}'.")

            else:
                logger.warning(f"File '{filename}' is still being written. Skipping.")

    def run(self):
        while True:
            current_month, current_date = self.get_current_month_and_date()

            base_path = self.construct_paths(current_month, current_date)

            if not os.path.exists(base_path):
                # logger.warning(f"Base directory '{base_path}' does not exist.")
                time.sleep(int(self.config["IterationSleepTime"]))
                continue

            self.copy_files(base_path)
            self.check_folder_all_files_exist(base_path)

            time.sleep(int(self.config["IterationSleepTime"]))

    def check_folder_all_files_exist(self, base_path):
        if base_path in self.processed_folders:
            return

        current_hour_range = self.get_current_hour_range()
        source_files = os.listdir(base_path)

        # Dictionary to store file groups based on creation time
        file_groups = {}

        for filename in source_files:
            source_file = os.path.join(base_path, filename)
            creation_time_range = self.get_hour_range_from_creation_time(source_file)

            if creation_time_range == current_hour_range:
                continue  # Skip files created in the current hour

            if creation_time_range not in file_groups:
                file_groups[creation_time_range] = [filename]
            else:
                file_groups[creation_time_range].append(filename)

        for hour_range, filenames in file_groups.items():
            destination_subdir = os.path.join(base_path, hour_range)

            # Check if all files in the group exist in the destination folder
            if all(os.path.exists(os.path.join(destination_subdir, filename)) for filename in filenames):
                logger.info(f"All files in the group created at {hour_range} exist in '{destination_subdir}'.")

        self.processed_folders.add(base_path)

    async def run_index(self, destination_subdir):
        # Your asynchronous logic here
        setproctitle.setproctitle("copy_script_run_index")

        command = f'sudo -u www-data php /var/www/cloud/occ files:scan -p /reflect/files/test/{destination_subdir}'

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait for the command to complete
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"Command executed successfully: {command}")
            else:
                logger.error(f"Error executing command: {command}, stderr: {stderr.decode()}")

        except asyncio.CancelledError:
            logger.warning("Command execution was cancelled.")
        except Exception as e:
            logger.error(f"Error executing command: {command}, {e}")

    def get_hour_range_from_creation_time(self, file_path):
        try:
            creation_time = os.path.getctime(file_path)
            creation_datetime = datetime.fromtimestamp(creation_time, self.timezone_moscow)
            hour_range = f"{creation_datetime.hour}-{creation_datetime.hour + 1}"
            logger.info(f"File: {file_path}, Creation Time: {creation_datetime}, Hour Range: {hour_range}")
            # print(f"File: {file_path}, Creation Time: {creation_datetime}, Hour Range: {hour_range}")
            return hour_range
        except Exception as e:
            logger.error(f"Error retrieving creation time for '{file_path}': {e}")
            return None

    def get_current_hour_range(self):
        current_hour = datetime.now(self.timezone_moscow).hour
        return f"{current_hour}-{current_hour + 1}"

    def get_previous_hour_range(self):
        current_hour = datetime.now(self.timezone_moscow).hour
        previous_hour = (current_hour - 1) % 24  # Handle the case when the current hour is 0
        return f"{previous_hour}-{previous_hour + 1}"


def read_config():
    config = ConfigParser()
    config.read('copy_script_config.ini')
    return config['Settings']


if __name__ == "__main__":
    config = read_config()
    log_file_name = config.get("LogFile")
    logger.add(log_file_name,
               format="{time} {level} {message}",
               rotation="10 MB",
               level="INFO")

    config = read_config()

    file_copier = FileCopier(config)
    file_copier.run()
