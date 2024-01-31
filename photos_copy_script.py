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

    def construct_paths(self, current_month, current_date, hour_range):
        base_path = os.path.join(
            self.config["BaseDirPath"],
            self.config["Studio_name"],
            f'{current_month} {self.config["Studio_name"].upper()}',
            current_date,
            hour_range
        )
        return base_path

    def copy_file(self, source_file, destination_path):
        filename = os.path.basename(source_file)
        destination_file = os.path.join(destination_path, filename)

        if not os.path.exists(destination_file):
            try:
                os.makedirs(destination_path, exist_ok=True)
                shutil.copy2(source_file, destination_file)
                logger.info(f"File '{filename}' copied to '{destination_path}'.")
            except Exception as e:
                print(e)

    def copy_files(self, base_path):

        allowed_extension = self.config["FileExtension"].lower()

        for filename in os.listdir(base_path):
            source_file = os.path.join(base_path, filename)

            if not (os.path.isfile(source_file) and filename.lower().endswith(allowed_extension)):
                continue  # Skip files that don't have the allowed extension

            creation_date = datetime.fromtimestamp(os.path.getctime(source_file), self.timezone_moscow).strftime(
                '%d.%m')
            current_date = self.get_current_month_and_date()[1]

            if creation_date != current_date:
                continue

            # Process only files with the allowed extension at the source folder level
            initial_size = os.path.getsize(source_file)
            time.sleep(int(self.config["FileSizeCheckInterval"]))
            current_size = os.path.getsize(source_file)

            if initial_size == current_size:
                destination_hour_range = self.get_hour_range_from_creation_time(source_file)

                if not destination_hour_range:
                    logger.warning(f"Skipped file '{filename}' due to invalid creation time.")
                    continue

                current_month, current_date = self.get_current_month_and_date()
                destination_path = self.construct_paths(current_month, current_date, destination_hour_range)

                self.copy_file(source_file, destination_path)
                return destination_path

            else:
                logger.warning(f"File '{filename}' is still being written. Skipping.")

    def run(self):
        while True:
            self.clear_processed_folders_if_new_day()

            current_month, current_date = self.get_current_month_and_date()
            base_path = self.construct_paths(current_month, current_date)

            studio_root_path = os.path.join(self.config["BaseDirPath"], self.config["Studio_name"])

            if not os.path.exists(studio_root_path):
                time.sleep(int(self.config["IterationSleepTime"]))
                continue

            destination_path = self.copy_files(studio_root_path)
            if destination_path:
                self.check_folder_all_files_exist(studio_root_path, destination_path)

            time.sleep(int(self.config["IterationSleepTime"]))

    def check_folder_all_files_exist(self, base_path, destination_path):

        logger.info(f"processed_folders: {self.processed_folders}")
        logger.info(f"destination_path: {destination_path}")

        destination_path_for_check = destination_path.replace('/cloud', '')

        if destination_path_for_check in self.processed_folders:
            return

        current_hour_range = self.get_current_hour_range()
        source_files = [f for f in os.listdir(base_path) if os.path.isfile(os.path.join(base_path, f))]

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
                asyncio.run(self.run_index(destination_subdir, base_path))

    async def run_index(self, destination_subdir, base_path):
        setproctitle.setproctitle("copy_script_run_index")

        formatted_dest_subdir = self.modify_path_for_index(destination_subdir)

        command = f'sudo -u www-data php /var/www/cloud/occ files:scan -p {formatted_dest_subdir}'

        logger.info(f"command: {command}")

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
                self.processed_folders.add(base_path)
            else:
                logger.error(f"Error executing command: {command}, stderr: {stderr.decode()}")

            logger.info(f"Console output: {process.stdout}")

        except asyncio.CancelledError:
            logger.warning("Command execution was cancelled.")
        except Exception as e:
            logger.error(f"Error executing command: {command}, {e}")

    def modify_path_for_index(self, destination_subdir):
        destination_subdir = destination_subdir.replace('/cloud', '')
        studio = self.config["Studio_name"]
        parts = destination_subdir.split(studio)

        second_part = parts[1]
        month_studio_part = second_part.split("/")[1]
        month_studio_part_quoted = f'"{month_studio_part}"'
        new_second_part = second_part.replace(month_studio_part, month_studio_part_quoted)
        return parts[0] + studio + new_second_part

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

    def get_previous_hour_range(self):
        current_hour = datetime.now(self.timezone_moscow).hour
        previous_hour = (current_hour - 1) % 24  # Handle the case when the current hour is 0
        return f"{previous_hour}-{previous_hour + 1}"

    def clear_processed_folders_if_new_day(self):
        current_date = datetime.now(self.timezone_moscow).strftime('%d.%m')
        if current_date != getattr(self, '_last_checked_date', None):
            self.processed_folders.clear()
            self._last_checked_date = current_date
            logger.info(f"Cleared processed folders for new day: {current_date}")


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
