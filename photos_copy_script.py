import os
import shutil
import subprocess
import time
import asyncio
import argparse
import json

from datetime import datetime
from configparser import ConfigParser

import pytz
import setproctitle

from loguru import logger

parser = argparse.ArgumentParser(description='Script for copying and indexing files.')
parser.add_argument('--studio', required=True, help='Studio name')
args = parser.parse_args()


class FileCopier:
    def __init__(self, config):
        self.destination_path = None
        self.config = config
        self.timezone_moscow = pytz.timezone('Europe/Moscow')  # Set Moscow timezone
        # saved_data = self.load_processed_folders()
        self.processed_folders = []
        # self._last_checked_date = saved_data.get('last_checked_date')

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

    def process_files(self, base_path):

        allowed_extension = self.config["FileExtension"].lower()

        for filename in os.listdir(base_path):

            logger.info(f"files: '{os.listdir(base_path)}'")

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
            current_size = os.path.getsize(source_file)

            if initial_size == current_size:
                destination_hour_range = self.get_hour_range_from_creation_time(source_file)

                if not destination_hour_range:
                    logger.warning(f"Skipped file '{filename}' due to invalid creation time.")
                    continue

                current_month, current_date = self.get_current_month_and_date()
                destination_path = self.construct_paths(current_month, current_date, destination_hour_range)

                self.copy_file(source_file, destination_path)
                self.destination_path = destination_path

            else:
                self.destination_path = None
                logger.warning(f"File '{filename}' is still being written. Skipping.")

    def run(self):
        self.loop = asyncio.get_event_loop()

        while True:
            self.update_processed_folders()

            studio_root_path = os.path.join(self.config["BaseDirPath"], self.config["Studio_name"])

            if not os.path.exists(studio_root_path):
                time.sleep(int(self.config["IterationSleepTime"]))
                continue

            self.process_files(studio_root_path)
            if self.destination_path:
                self.check_folder_all_files_exist(studio_root_path)

                # loop.run_until_complete(self.run_index(self.destination_path, studio_root_path))

            time.sleep(int(self.config["IterationSleepTime"]))

    def check_folder_all_files_exist(self, base_path):

        logger.info(f"processed_folders: {self.processed_folders}")
        logger.info(f"destination_path: {self.destination_path}")

        # destination_path_for_check = self.destination_path.replace('/cloud', '')

        logger.info(f"destination_path in self.processed_folders: "
                    f"{self.destination_path in self.processed_folders}")

        if self.destination_path in self.processed_folders:
            logger.info(f"{self.destination_path} exists in processed_folders")
            return

        current_hour_range = self.get_current_hour_range()
        source_files = [f for f in os.listdir(base_path) if os.path.isfile(os.path.join(base_path, f))]

        # Dictionary to store file groups based on creation time
        file_groups = {}

        for filename in source_files:
            source_file = os.path.join(base_path, filename)
            creation_time_range = self.get_hour_range_from_creation_time(source_file)

            creation_date = datetime.fromtimestamp(os.path.getctime(source_file), self.timezone_moscow).strftime(
                '%d.%m')
            current_date = self.get_current_month_and_date()[1]

            if creation_date != current_date:
                continue

            if creation_time_range == current_hour_range:
                logger.info('file created this hour range')
                continue  # Skip files created in the current hour

            if creation_time_range not in file_groups:
                file_groups[creation_time_range] = [filename]
            else:
                file_groups[creation_time_range].append(filename)

        for hour_range, filenames in file_groups.items():
            logger.info(f"filenames: {filenames}")

            # Check if all files in the group exist in the destination folder

            for filename in filenames:
                logger.info(f"dest_file_path: {os.path.join(self.destination_path, filename)}")

            logger.info(f"all files exist in dest folder:"
                        f"{all(os.path.exists(os.path.join(self.destination_path, filename)) for filename in filenames)}")

            if all(os.path.exists(os.path.join(self.destination_path, filename)) for filename in filenames):
                logger.info('before start index')
                self.run_index(self.destination_path)

    def run_index(self, destination_subdir):
        setproctitle.setproctitle("copy_script_run_index")

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
                self.processed_folders.append(destination_subdir)
                self.save_processed_folders()
            else:
                logger.error(f"Error executing command: {command}, stderr: {process.stderr.decode()}")

            logger.info(f"Console output: {process.stdout.decode()}")

        except Exception as e:
            logger.error(f"Error executing command: {command}, {e}")

    # async def main(self, destination_path, base_path):
    #     setproctitle.setproctitle("copy_script_run_index")
    #
    #     formatted_dest_subdir = self.modify_path_for_index(destination_path)
    #
    #     command = f'sudo -u www-data php /var/www/cloud/occ files:scan -p {formatted_dest_subdir}'
    #
    #     logger.info(f"command: {command}")
    #
    #     try:
    #         process = await asyncio.create_subprocess_shell(
    #             command,
    #             stdout=asyncio.subprocess.PIPE,
    #             stderr=asyncio.subprocess.PIPE
    #         )
    #
    #         # Wait for the command to complete
    #         stdout, stderr = await process.communicate()
    #
    #         if process.returncode == 0:
    #             logger.info(f"Command executed successfully: {command}")
    #             self.processed_folders.append(destination_path)
    #             self.save_processed_folders()
    #         else:
    #             logger.error(f"Error executing command: {command}, stderr: {stderr.decode()}")
    #
    #         logger.info(f"Console output: {process.stdout}")
    #
    #     except asyncio.CancelledError:
    #         logger.warning("Command execution was cancelled.")
    #     except Exception as e:
    #         logger.error(f"Error executing command: {command}, {e}")
    #
    # async def run_index(self, destination_subdir, base_path):
    #     await self.main(destination_subdir, base_path)

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

    def update_processed_folders(self):
        current_date = datetime.now(self.timezone_moscow).strftime('%d.%m')
        processed_data = self.load_processed_folders()
        process_date = processed_data.get('process_date')
        processed_folders = processed_data.get('folders_path')

        if process_date:
            logger.info(f"Processed date: {process_date}")
            logger.info(f"Current date: {current_date}")
            logger.info(f"Processed folders: {processed_folders}")
            self.processed_folders = processed_folders

            if process_date == current_date:
                self.processed_folders = processed_folders
            else:
                self.clear_processed_folders()

    @staticmethod
    def load_processed_folders():
        try:
            with open('processed_folders.json', 'r') as file:
                data = json.load(file)
                return data
        except FileNotFoundError:
            return {'process_date': None, 'processed_folders': []}

    def save_processed_folders(self):
        current_date = datetime.now(self.timezone_moscow).strftime('%d.%m')

        data = {
            'process_date': current_date,
            'folders_path': list(self.processed_folders)
        }

        with open('processed_folders.json', 'w') as file:
            json.dump(data, file)

    @staticmethod
    def clear_processed_folders():
        with open('processed_folders.json', 'w') as json_file:
            json.dump({}, json_file)


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
               compression='zip',
               level="INFO")

    config['Studio_name'] = args.studio  # Set the studio name based on the command-line argument

    file_copier = FileCopier(config)
    file_copier.run()

