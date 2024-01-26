import os
import shutil
from datetime import datetime
import time
from configparser import ConfigParser

class FileCopier:
    def __init__(self, config):
        self.config = config

    def get_current_month_and_date(self):
        current_month_ru = datetime.now().strftime('%B')
        current_month = self.translate_month_to_russian(current_month_ru)
        current_date = datetime.now().strftime('%d.%m')
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
        for filename in os.listdir(base_path):
            source_file = os.path.join(base_path, filename)

            initial_size = os.path.getsize(source_file)
            time.sleep(int(self.config["FileSizeCheckInterval"]))
            current_size = os.path.getsize(source_file)

            if initial_size == current_size:
                destination_hour_range = self.get_hour_range_from_creation_time(source_file)

                if not destination_hour_range:
                    print(f"Skipped file '{filename}' due to invalid creation time.")
                    continue

                destination_subdir = os.path.join(base_path, destination_hour_range)
                os.makedirs(destination_subdir, exist_ok=True)

                destination_file = os.path.join(destination_subdir, filename)

                if os.path.exists(destination_file):
                    print(f"File '{filename}' already exists in '{destination_subdir}'.")
                else:
                    shutil.copy2(source_file, destination_file)
                    print(f"File '{filename}' copied to '{destination_subdir}'.")
            else:
                print(f"File '{filename}' is still being written. Skipping.")

    def run(self):
        while True:
            current_month, current_date = self.get_current_month_and_date()

            base_path = self.construct_paths(current_month, current_date)

            if not os.path.exists(base_path):
                print(f"Base directory '{base_path}' does not exist.")
                time.sleep(int(self.config["IterationSleepTime"]))
                continue

            self.copy_files(base_path)

            time.sleep(int(self.config["IterationSleepTime"]))

    @staticmethod
    def get_hour_range_from_creation_time(file_path):
        try:
            creation_time = os.path.getctime(file_path)
            creation_datetime = datetime.fromtimestamp(creation_time)
            hour_range = f"{creation_datetime.hour}-{creation_datetime.hour + 1}"
            return hour_range
        except Exception as e:
            print(f"Error retrieving creation time for '{file_path}': {e}")
            return None

def read_config():
    config = ConfigParser()
    config.read('copy_script_config.ini')
    return config['Settings']

if __name__ == "__main__":
    config = read_config()

    file_copier = FileCopier(config)
    file_copier.run()
