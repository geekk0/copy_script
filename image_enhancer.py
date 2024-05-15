import os
import re
import subprocess
import time

import pytz
import json
from datetime import datetime, date
from loguru import logger

from PIL import Image, ImageEnhance, ImageOps, ExifTags, ImageFilter
from configparser import ConfigParser, NoSectionError


class ImageEnhancer:
    def __init__(self, settings):
        self.studio = settings['path_settings']['Studio_name']
        self.photos_path = settings['path_settings']['BaseDirPath']
        self.files_extension = settings['path_settings']['FileExtension']
        self.contrast_value = float(settings['image_settings']['Contrast'])
        self.brightness_value = float(settings['image_settings']['Brightness'])
        self.color_saturation_value = float(settings['image_settings']['ColorSaturation'])
        self.sharpness = float(settings['image_settings']['Sharpness'])
        self.temperature = float(settings['image_settings']['Temperature'])
        self.sharp_filter = settings['image_settings'].getboolean('SharpFilter')
        self.blur_filter = settings['image_settings'].getboolean('BlurFilter')
        self.quality = int(settings['image_settings']['Quality'])
        self.timezone_moscow = pytz.timezone('Europe/Moscow')

    def enhance_image(self, im):
        enhancer = ImageEnhance.Sharpness(im)
        im = enhancer.enhance(self.sharpness)
        enhancer = ImageEnhance.Color(im)
        im = enhancer.enhance(self.color_saturation_value)
        enhancer = ImageEnhance.Brightness(im)
        im = enhancer.enhance(self.brightness_value)
        enhancer = ImageEnhance.Contrast(im)
        im = enhancer.enhance(self.contrast_value)

        return im

    def adjust_image_temperature(self, image):

        if image.mode != 'RGB':
            image = image.convert('RGB')
        r, g, b = image.split()

        if self.temperature < 0:  # cool down
            r = r.point(lambda i: max(0, i + self.temperature))
            b = b.point(lambda i: min(255, i - self.temperature))
        else:  # warm up
            r = r.point(lambda i: min(255, i + self.temperature))
            b = b.point(lambda i: max(0, i - self.temperature))

        return Image.merge('RGB', (r, g, b))

    @staticmethod
    def colorize_image(image):
        if image.mode != 'L':
            image = image.convert('L')
        tinted_image = ImageOps.colorize(image, 'black', 'blue')
        return tinted_image

    @staticmethod
    def is_not_black_white(image):

        if image.mode != 'RGB':
            image = image.convert('RGB')

        colors = set(image.getdata())

        return False if len(colors) < 600 else True

    def enhance_folder(self, folder):
        logger.debug(f'enhance folder: {folder}')
        for item in os.listdir(folder):
            item_path = os.path.join(folder, item)
            if os.path.isfile(item_path):
                with open(item_path, 'rb') as f:
                    image = Image.open(f)

                    original_exif = image.info.get('exif', b'')

                    if self.is_not_black_white(image):
                        logger.debug(f'enhancing file: {item_path}')
                        adjusted_image_temp_content = self.adjust_image_temperature(image)
                        enhanced_image_content = self.enhance_image(adjusted_image_temp_content)
                        self.save_image(enhanced_image_content, item_path, original_exif)
                    else:
                        logger.debug(f'black-white: {item_path}')
        self.save_enhanced_folders(folder)

    @staticmethod
    def rename_folder(folder):
        new_folder = f'{folder}_RS'
        os.rename(folder, new_folder)
        return new_folder

    @staticmethod
    def chown_folder(folder_path):
        command = f'sudo chown -R www-data:www-data "{folder_path}"'
        os.system(command)

    @staticmethod
    def index_folder(folder_path):
        path = folder_path.replace('/cloud', '')
        command = f'sudo -u www-data php /var/www/cloud/occ files:scan -p "{path}" --shallow'
        os.system(command)

    def save_image(self, im, file_path, original_exif):
        if self.sharp_filter:
            logger.debug("sharp filter enabled")
            im = im.filter(ImageFilter.SHARPEN)
        elif self.blur_filter:
            logger.debug("blur filter enabled")
            im = im.filter(ImageFilter.GaussianBlur(1.3))
        im.save(file_path, dpi=(300, 300), quality=self.quality, exif=original_exif, subsampling=0)

        logger.debug(f'saved file:{file_path}')

    @staticmethod
    def print_metadata(image):
        # Get the original image's EXIF data
        exif_data = image._getexif()

        # Decode the EXIF data
        if exif_data is not None:
            for tag, value in exif_data.items():
                tag_name = ExifTags.TAGS.get(tag, tag)
                if tag_name != "MakerNote":
                    logger.debug(f"{tag_name}: {value}")

    def run(self):
        if not os.path.exists(self.photos_path):
            logger.error(f'Folder {self.photos_path} does not exist')
            return
        today_folders = self.get_folders_modified_today()
        logger.debug(f'today folders: {today_folders}')
        for folder in today_folders:
            if self.check_not_enhanced_yet(folder):
                if self.check_folder_not_in_process(folder):
                    self.enhance_folder(folder)
                    new_folder = self.rename_folder(folder)
                    self.chown_folder(new_folder)
                    self.index_folder(new_folder)

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
        enhanced_folders = self.load_enhanced_folders().get('enhanced_folders')
        if not enhanced_folders:
            return True
        return folder not in self.load_enhanced_folders().get('enhanced_folders')

    @staticmethod
    def check_folder_not_in_process(folder):
        num_files_1 = sum([len(files) for root, dirs, files in os.walk(folder)])
        time.sleep(5)
        num_files_2 = sum([len(files) for root, dirs, files in os.walk(folder)])
        if num_files_2 == num_files_1:
            return True

    def update_enhanced_folders(self):
        current_date = datetime.now(self.timezone_moscow).strftime('%d.%m')
        processed_data = self.load_enhanced_folders()
        process_date = processed_data.get('date')

        if process_date:
            if process_date != current_date:
                self.clear_enhanced_folders()

    @staticmethod
    def load_enhanced_folders():
        filename = 'enhanced_folders.json'
        default_values = {'date': None, 'enhanced_folders': []}
        if not os.path.isfile(filename):
            return default_values
        try:
            with open(filename) as file:
                data = json.load(file)
                return data
        except json.decoder.JSONDecodeError:
            logger.debug("File does not contain valid JSON data. Returning default values.")
            return default_values

    def save_enhanced_folders(self, enhanced_folder):
        current_date = datetime.now(self.timezone_moscow).strftime('%d.%m')
        enhanced_folders = self.load_enhanced_folders().get('enhanced_folders') or []
        enhanced_folders.append(enhanced_folder)

        data = {
            'date': current_date,
            'enhanced_folders': list(enhanced_folders),
        }

        with open('enhanced_folders.json', 'w') as file:
            json.dump(data, file)

    @staticmethod
    def clear_enhanced_folders():
        with open('enhanced_folders.json', 'w') as json_file:
            json.dump({}, json_file)


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
            image_settings = config['ImageEnhancement']
            return {'path_settings': path_settings, 'image_settings': image_settings}
        else:
            return {'path_settings': path_settings}


if __name__ == '__main__':
    logger.add("image_enhancer.log",
               format="{time} {level} {message}",
               rotation="1 MB",
               compression='zip',
               level="INFO")
    studios_settings_files = get_settings_files()
    while True:
        for settings_file in studios_settings_files:
            logger.info(f'Processing settings file: {settings_file}')
            settings = read_settings_file(settings_file)
            if settings.get('image_settings'):
                image_enhancer = ImageEnhancer(settings)
                image_enhancer.update_enhanced_folders()
                image_enhancer.run()
                time.sleep(10)
            else:
                logger.info(f'Config file: {settings_file} does not contain image settings. Skipping...')





