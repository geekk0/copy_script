import os
import re
import subprocess
import multiprocessing
import setproctitle
import time

import pytz
import json
from datetime import datetime, date
from loguru import logger

from PIL import Image, ImageEnhance, ImageOps, ExifTags, ImageFilter
from configparser import ConfigParser, NoSectionError
from lockfile import write_to_common_file
from tg_bot import TelegramBot

class ImageEnhancer:
    def __init__(self, settings):
        self.studio = settings['path_settings']['Studio_name']
        self.photos_path = settings['path_settings']['BaseDirPath']
        self.files_extension = settings['path_settings']['FileExtension']
        self.contrast_value = float(settings['image_settings']['Contrast'])
        self.brightness_value = float(settings['image_settings']['Brightness'])
        self.bw_brightness_value = float(settings['image_settings']['BW_brightness'])
        self.bw_contrast_value = float(settings['image_settings']['BW_contrast'])
        self.color_saturation_value = float(settings['image_settings']['ColorSaturation'])
        self.sharpness = float(settings['image_settings']['Sharpness'])
        self.temperature = float(settings['image_settings']['Temperature'])
        self.sharp_filter = settings['image_settings'].getboolean('SharpFilter')
        self.blur_filter = settings['image_settings'].getboolean('BlurFilter')
        self.quality = int(settings['image_settings']['Quality'])
        self.studio_timezone = pytz.timezone(settings['path_settings']['TimeZoneName'])

    def enhance_image(self, im, black_white=None):
        if im.mode != 'RGB':
            im = im.convert('RGB')

        enhancer = ImageEnhance.Sharpness(im)
        im = enhancer.enhance(self.sharpness)
        if black_white:
            enhancer = ImageEnhance.Brightness(im)
            im = enhancer.enhance(self.bw_brightness_value)
            enhancer = ImageEnhance.Contrast(im)
            im = enhancer.enhance(self.bw_contrast_value)
        else:
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
    def is_black_white(image):

        if image.mode != 'RGB':
            image = image.convert('RGB')

        colors = set(image.getdata())

        return True if len(colors) < 600 else False

    def enhance_folder(self, folder):
        logger.debug(f'enhance folder: {folder}')
        new_folder = folder + '_RS'
        os.mkdir(new_folder)
        for item in os.listdir(folder):
            item_path = os.path.join(folder, item)
            if os.path.isfile(item_path):
                try:
                    with open(item_path, 'rb') as f:
                        image = Image.open(f)

                        original_exif = image.info.get('exif', b'')
                        logger.debug(f'enhancing file: {item_path}')

                        black_white = self.is_black_white(image)
                        if not black_white:
                            try:
                                image = self.adjust_image_temperature(image)
                            except Exception as e:
                                logger.error(f'Error adjusting image "{item}" temperature: {e}')
                        try:
                            enhanced_image_content = self.enhance_image(image, black_white=black_white)
                        except Exception as e:
                            logger.error(f'Error enhancing image "{item}": {e}')
                        try:
                            self.save_image(enhanced_image_content, item_path.replace(folder, new_folder),
                                            original_exif)
                        except Exception as e:
                            logger.error(f'Error saving enhanced image "{item}": {e}')
                except Exception as e:
                    logger.error(f'Error processing file "{item_path}": {e}')
            else:
                logger.error(f'not a file: {item_path}')

        try:
            self.save_enhanced_folders(folder)
        except Exception as e:
            logger.error(f'Error saving enhanced folders: {e}')

        return new_folder

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
                    try:
                        new_folder = self.enhance_folder(folder)
                        # new_folder = self.rename_folder(folder)
                        self.chown_folder(new_folder)
                        self.index_folder(new_folder)
                    except Exception as e:
                        logger.error(f'enhance folder {folder} error: {e}')

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
        if not os.path.exists(folder + "_RS"):
            return True

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

    def update_enhanced_folders(self):
        current_date = datetime.now(self.studio_timezone).strftime('%d.%m')
        logger.info(f'update_enhanced_folders current_date(studio timezone): {current_date}')
        logger.info(f"datetime.now: {datetime.now().strftime('%d.%m')}")

        processed_data = self.load_enhanced_folders()
        process_date = processed_data.get('date')

        if process_date:
            if process_date != current_date:
                self.clear_enhanced_folders()

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

        # with open('enhanced_folders.json', 'w') as file:
        #     json.dump(data, file)
        try:
            result = write_to_common_file(data, 'enhanced_folders.json')
            logger.info(f'write_to_common_file result: {result}')
        except Exception as e:
            logger.error(f'write_to_common_file error: {e}')



    @staticmethod
    def clear_enhanced_folders():
        write_to_common_file({}, 'enhanced_folders.json')
        # with open('enhanced_folders.json', 'w') as json_file:
        #     json.dump({}, json_file)


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


def run_image_enhancer(studio_settings_file: str):
    error_sent = False

    studio_name = (read_settings_file(studio_settings_file)
                   .get('path_settings').get('studio_name'))

    logger.add(f"{studio_name}_image_enhancer.log",
               format="{time} {level} {message}",
               rotation="1 MB",
               compression='zip',
               level="DEBUG")

    while True:
        studio_settings = read_settings_file(studio_settings_file)
        path_settings = studio_settings.get('path_settings')
        studio_name = path_settings.get('studio_name')
        logger.info(f"Starting {studio_name} image enhancer, time: {datetime.now().strftime('%H:%M:%S')}")

        try:
            image_enhancer = ImageEnhancer(studio_settings)
            image_enhancer.update_enhanced_folders()
            process_name = f"{studio_name}_image_enhancer"
            setproctitle.setproctitle(process_name)
            image_enhancer.run()
            time.sleep(15)
            error_sent = False
        except Exception as e:
            logger.error(f"Error run_image_enhancer: {e}")
            if not error_sent:
                tg_bot = TelegramBot()
                tg_bot.send_message_to_group(f"Error in {studio_name} image enhancer: {e}")
                error_sent = True
            time.sleep(15)


if __name__ == '__main__':
    studios_as_args = []
    studios_settings_files = get_settings_files()
    for settings_file in studios_settings_files:
        settings = read_settings_file(settings_file)
        if (settings.get('image_settings') and
                settings.get('image_settings').get('enhancer') != 'ai_enhancer'):
            studios_as_args.append(settings_file)
    with multiprocessing.Pool() as pool:
        pool.starmap(run_image_enhancer, [(arg,) for arg in studios_as_args])









