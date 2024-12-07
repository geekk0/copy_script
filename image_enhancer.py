import os
import multiprocessing
import setproctitle
import time

import pytz
import json
from datetime import datetime
from loguru import logger

from PIL import Image, ImageEnhance, ImageOps, ExifTags, ImageFilter
from configparser import ConfigParser, NoSectionError
from tg_bot import TelegramBot
from photos_copy_script import FileCopier, read_config


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
        self.settings = settings

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
    def is_black_white(image):

        if image.mode != 'RGB':
            image = image.convert('RGB')

        colors = set(image.getdata())

        return True if len(colors) < 600 else False

    def enhance_folder(self, folder):
        if not os.path.exists(folder):
            # self.remove_from_processed_folders(folder.split('/')[-1])
            # logger.info(f'Hour range {folder.split('/')[-1]} of folder {folder} removed from processed folders')
            return
        logger.debug(f'enhance folder: {folder}')
        new_folder = folder + '_RS'
        if not os.path.exists(new_folder):
            os.mkdir(new_folder)
        for item in os.listdir(folder):
            if os.path.isfile(os.path.join(new_folder, item)):
                continue
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

        return new_folder

    @staticmethod
    def check_full_folder(folder_path):
        num_source_files = len([f for f in os.listdir(folder_path)
                                if os.path.isfile(os.path.join(folder_path, f))])
        num_enhanced_files = len([f for f in os.listdir(folder_path + '_RS')
                                if os.path.isfile(os.path.join(folder_path + '_RS', f))])
        if num_enhanced_files >= num_source_files:
            return True

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

    def run(self):
        if not os.path.exists(self.photos_path):
            logger.error(f'Folder {self.photos_path} does not exist')
            return
        today_folders = self.get_ready_folders_list()
        logger.debug(f'folders to enhance: {today_folders}')
        if not today_folders:
            return

        self.index_ready_folders(today_folders)

        for folder in today_folders:
            try:
                new_folder = self.enhance_folder(folder)
                folder_is_full = self.check_full_folder(folder)

                logger.info(f'folder {folder} is_full: {folder_is_full}')
                logger.info(f'new_folder: {new_folder}')

                if not (new_folder and folder_is_full):
                    continue
                self.chown_folder(new_folder)
                self.index_folder(new_folder)
                self.remove_from_processed_folders(folder.split('/')[-1])

            except Exception as e:
                logger.error(f'enhance folder {folder} error: {e}')

    def index_ready_folders(self, ready_folders):
        for folder in ready_folders:
            try:
                self.chown_folder(folder)
                self.index_folder(folder)
            except Exception as e:
                logger.error(f'Error indexing folder {folder}: {e}')

    def get_ready_folders_list(self):

        ready_folders = []

        hour_ranges = self.get_hour_ranges_from_processed_folders()

        for hour_range in hour_ranges:
            try:
                config = self.settings['path_settings']
                logger.debug(f'studio: {config["Studio_name"]}')
                file_copier = FileCopier(config)
                current_month, current_date = file_copier.get_current_month_and_date()
                folder_path = file_copier.construct_paths(current_month, current_date, hour_range)

                logger.debug(f'folder path: {folder_path}')
                if folder_path not in ready_folders:
                    ready_folders.append(folder_path)
            except Exception as e:
                logger.error(f'Error constructing paths: {e}')

        return ready_folders

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
    settings_files = [os.path.join(os.getcwd(), file) for file
                      in os.listdir(os.getcwd()) if file.endswith('_config.ini')]
    # settings_files = ['/cloud/copy_script/test_studio_config.ini']
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
            process_name = f"{studio_name}_image_enhancer"
            setproctitle.setproctitle(process_name)
            image_enhancer.run()
            time.sleep(15)
            error_sent = False
        except Exception as e:
            logger.error(f"Error run_image_enhancer: {e}")
            # if not error_sent:
            #     tg_bot = TelegramBot()
            #     tg_bot.send_message_to_group(f"Error in {studio_name} image enhancer: {e}")
            #     error_sent = True
            time.sleep(15)


if __name__ == '__main__':
    studios_as_args = []
    studios_settings_files = get_settings_files()
    for settings_file in studios_settings_files:
        settings = read_settings_file(settings_file)
        if (settings.get('image_settings') and
                settings.get('image_settings').get('enhancer') not in ['ai_enhancer', 'ai_enhancer_bot_only']):
            studios_as_args.append(settings_file)
    with multiprocessing.Pool() as pool:
        pool.starmap(run_image_enhancer, [(arg,) for arg in studios_as_args])









