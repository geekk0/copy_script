import configparser
import os

import telebot
import subprocess
import pwd
import grp
import json
import time

from os import environ
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

class TelegramBot:
    load_dotenv()
    token = environ.get("BOT_TOKEN")
    bot = telebot.TeleBot(token)
    chat_id = int(environ.get('REFLECT_GROUP_CHAT_ID'))
    studios = ['Силуэт', 'Портрет(ЗАЛ)', 'Отражение', 'Reflect KZ', 'test_studio']
    current_level_folders = []
    base_path = '/cloud/reflect/files'
    current_path = ''

    def __init__(self):
        self.selected_studio = None
        self.current_config_file = None
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_callback_query)
        self.bot.message_handler(commands=['start'])(self.handle_start)
        self.bot.message_handler(func=lambda message: message.reply_to_message is not None)(self.handle_reply)
        self.shared_folders = []
        self.mailing_date = ''
        self.image_section = []
        self.mode = None

    def start_polling(self):
        self.bot.polling()

    def handle_start(self, message, call=None):

        if message.chat.id != self.chat_id:
            self.bot.reply_to(message, "Доступ только из группы")
            self.write_to_log(
                message=f"""
                    current_chat_id: {message.chat.id},
                    admin_chat_id: {self.chat_id}
                """
            )
            return

        self.current_path = ''
        self.selected_studio = None
        self.current_config_file = None

        if message.content_type == 'text':
            keyboard = self.create_keyboard(['Индексация', 'Рассылка', 'Обработка', 'ИИ обработка'],
                                           ['indexing', 'mailing', 'enhancement', 'ai_enhancement'],
                                            no_home_btn=True)
            if call:
                self.update_message(call, "Выберите действие:", keyboard)
            else:
                self.bot.send_message(message.chat.id, "Выберите действие:", reply_markup=keyboard)

    def handle_callback_query(self, call):

        # keywords = ["mailing:", "indexing:", "enhancement:", "ai_enhancement:"]

        self.write_to_log(call.data)

        if call.message.chat.id != self.chat_id:
            return

        elif call.data == "home_clicked":
            self.handle_start(call.message, call)

        elif call.data in ["indexing", "mailing", "enhancement", "ai_enhancement"]:
            self.show_studio_select(call)

        elif self.mode == 'enhancement':
            if not self.selected_studio:
                self.selected_studio = call.data
            elif 'image_settings/' in call.data:
                self.get_new_value_from_user(call)
            else:
                self.get_studio_image_settings(call)

        elif self.mode == 'ai_enhancement':
            if not self.selected_studio:
                self.selected_studio = call.data
            elif self.selected_studio and not self.current_path:
                self.list_studio_folders(call)
            # elif self.check_exists_folders_inside(call.message):
            #     self.show_next_folder(call)
            # elif self.current_path and (call.data not in self.current_path):
            #     self.current_path += f"/{call.data}"
            # else:
            #     self.add_to_ai_queue(self.current_path)

        # elif self.mode == 'enhancement' and self.selected_studio:
        #     self.show_studio_image_settings(call)
        #
        # elif self.mode and not self.selected_studio:
        #     if call.data in self.studios:
        #         self.show_studio_folders(call)
        #
        # elif self.selected_studio and not self.current_path:
        #     self.current_path += f"/{call.data}"
        #
        # elif 'delete:record' in call.data:
        #     self.delete_record(call)
        #
        # elif 'record' in call.data:
        #     self.handle_record(call)
        #
        # else:
        #
        #     if 'image_settings/' in call.data:
        #         self.get_new_value_from_user(call)
        #
        #     elif call.data not in self.current_path:
        #         self.current_path += f"/{call.data}"
        #     elif self.check_exists_folders_inside(call.message):
        #         self.show_next_folder(call)
        #     else:
        #         if self.mode == 'indexing':
        #             self.call_index(call)
        #         elif self.mode == 'ai_enhancement':
        #             self.add_to_ai_queue(self.current_path)
        #             self.update_message(call, text=f'Папка {self.current_path} добавлена '
        #                                            f'в начало очереди ИИ обработки')

    def handle_reply(self, message):

        setting = message.reply_to_message.text.split(':')[0].split(' ')[2]
        value = message.text

        if 'filter' in setting:
            if value.lower() == 'true' or value.lower() == 'false':
                self.write_settings_file(setting, value)
                self.image_section[setting] = value
                text = f"Значение {setting}: {value} установлено"
            else:
                text = "Новое значение должно быть True или False"

        else:
            try:
                float(value)
                self.write_settings_file(setting, value)
                self.image_section[setting] = value
                text = f"Значение {setting}: {value} установлено"

            except ValueError:
                text = "Новое значение должно быть числом"

        keyboard = self.show_section_settings(self.image_section)
        self.bot.send_message(message.chat.id, text, reply_markup=keyboard)

    def notify_admin_folder_ready(self, folder, download_url):
        message = f'Папка {folder} доступна для скачивания по ссылке: {download_url}'
        self.bot.send_message(self.chat_id, message)

    def send_message_to_group(self, message):
        self.bot.send_message(self.chat_id, message)

    # def run_index(self, root_folder=False):
    #     sudo_password = environ.get('SUDOP')
    #     full_path = self.current_path
    #     path = self.current_path.replace('/cloud', '')
    #     if root_folder:
    #         studio_root_path = os.path.join(self.base_path, self.selected_studio)
    #         path = studio_root_path.replace('/cloud', '')
    #     command = f"echo {sudo_password} | sudo -S -u www-data php /var/www/cloud/occ files:scan -p '{path}' --shallow"
    #     self.current_path = os.path.dirname(self.current_path)
    #     self.write_to_log(command)
    #
    #     process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #     output, error = process.communicate()
    #
    #     if process.returncode == 0:
    #         if not root_folder:
    #             self.write_to_log(output)
    #             self.update_processed_folders(full_path)
    #             self.run_index(root_folder=True)
    #         else:
    #             return "Индексация произведена успешно"
    #
    #     else:
    #         self.write_to_log(f'output: {output}, error: {error}')
    #         return "Ошибка индексации"

    def run_index(self):
        sudo_password = environ.get('SUDOP')
        full_path = self.current_path
        path = self.current_path.replace('/cloud', '')
        command = f"echo {sudo_password} | sudo -S -u www-data php /var/www/cloud/occ files:scan -p '{path}' --shallow"
        self.current_path = os.path.dirname(self.current_path)
        self.write_to_log(command)

        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()

        if process.returncode == 0:
            self.write_to_log(output)
            self.update_processed_folders(full_path)
            return "Индексация произведена успешно"

        else:
            self.write_to_log(f'output: {output}, error: {error}')
            return "Ошибка индексации"

    def change_ownership(self, user='www-data', group='www-data'):
        directory_path = self.current_path
        try:
            uid = pwd.getpwnam(user).pw_uid
            gid = grp.getgrnam(group).gr_gid

            while directory_path != '/':
                os.chown(directory_path, uid, gid)
                directory_path = os.path.dirname(directory_path)

        except Exception as e:
            self.write_to_log(f"Error changing ownership of '{directory_path}' and its parent directories: {e}")

    def update_processed_folders(self, full_path):
        processed_folders_file_path = (os.path.join(f'/cloud/copy_script',
                                                    f'processed_folders_{self.selected_studio}.json'))
        try:
            with open(processed_folders_file_path, "r+") as processed_folders_file:
                processed_data = json.load(processed_folders_file)
                processed_folders = processed_data.get('already_indexed', [])

                if self.current_path not in processed_folders:
                    processed_folders.append(full_path)
                    processed_data['already_indexed'] = processed_folders

                    processed_folders_file.seek(0)
                    json.dump(processed_data, processed_folders_file)
                    processed_folders_file.truncate()

        except json.decoder.JSONDecodeError as e:
            self.write_to_log(f"Error decoding JSON: {e}")
        except Exception as e:
            self.write_to_log(f"Error loading processed folders: {e}")

    def get_studio_shared_folders(self, call):

        shared_folder_file = self.selected_studio + "_рассылка.json"
        if os.path.exists(os.path.join('/cloud/reflect/files/Рассылка', shared_folder_file)):
            try:
                with open(os.path.join('/cloud/reflect/files/Рассылка', shared_folder_file), "r+") as mailing_file:
                    data = json.load(mailing_file)
                    self.mailing_date = data.get('date')
                    self.shared_folders = data.get('shared_folders')
                    keyboard = self.create_keyboard([x.get('client_name') + '\n' + x.get('client_phone_number')
                                                     for x in self.shared_folders],
                                                    ['record' + x.get('client_name') + ' ' +
                                                     x.get('client_phone_number')
                                                     for x in self.shared_folders])
                    self.update_message(call, text=f'Рассылка за {self.mailing_date}', keyboard=keyboard)
            except Exception as e:
                self.write_to_log(f'error reading mailing file: {e}')
        else:
            keyboard = InlineKeyboardMarkup()
            home_button = InlineKeyboardButton(text="🏠", callback_data="home_clicked")
            keyboard.add(home_button)
            self.update_message(call, text="Нет файла рассылки", keyboard=keyboard)

    def get_studio_config_file(self):
        studio_configs = {
            'Отражение': 'reflect_config.ini',
                          'Портрет(ЗАЛ)': 'portrait_config.ini',
                          'Силуэт': 'silhouette_config.ini',
                          'Reflect KZ': 'kz_config.ini',
                          'test_studio': 'test_studio_config.ini',
                          }

        studio_config_file_path = (os.path.join(f'/cloud/copy_script',
                                                studio_configs[self.selected_studio]))

        if os.path.exists(studio_config_file_path):
            return studio_config_file_path
        else:
            self.write_to_log(f'config file not found: {studio_config_file_path}')

    def get_studio_image_settings(self, call=None):

        self.write_to_log('get_studio_image_settings')

        studio_config_file_path = self.get_studio_config_file()

        if os.path.exists(studio_config_file_path):

            self.current_config_file = studio_config_file_path

            settings = self.read_settings_file(studio_config_file_path)

            self.image_section = settings.get('image_settings')

            self.show_section_settings(self.image_section, call)

    @staticmethod
    def read_settings_file(settings_file):
        with open(settings_file, 'r', encoding='utf-8') as file:
            config = configparser.ConfigParser()
            config.read_file(file)
            path_settings = config['Settings']
            if config.has_section('ImageEnhancement'):
                image_settings = config['ImageEnhancement']
                return {'path_settings': path_settings, 'image_settings': image_settings}
            else:
                return {'path_settings': path_settings}

    def write_settings_file(self, key, value):
        config = configparser.ConfigParser()
        config.read(self.current_config_file)
        config.set('ImageEnhancement', key, value)

        with open(self.current_config_file, 'w', encoding='utf-8') as file:
            config.write(file)

    def show_section_settings(self, section, call=None):
        section_settings_keys = []
        section_settings_items = []
        if section:
            for key in section:
                section_settings_keys.append(key)
                section_settings_items.append(f"image_settings/{key}: {section[key]}")
            keyboard = self.create_keyboard(section_settings_keys, section_settings_items)

            if call:
                self.update_message(call, text=f"Настройки изображений ({self.selected_studio}):",
                                    keyboard=keyboard)
            else:
                return keyboard
        else:
            self.update_message(call, text=f'Настройки обработки изображений'
                                           f'для студии "{self.selected_studio}" отсутствуют',
                                keyboard=call.message.reply_markup)

    def show_studio_select(self, call):
        text = "Выберите студию:"
        self.mode = call.data
        keyboard = self.create_keyboard(self.studios, self.studios)
        self.update_message(call, text, keyboard)

    def show_studio_folders(self, call):


        self.write_to_log(f'show_studio_folders: self.mode = {self.mode}')

        # if self.mode == "indexing" or "ai_enhancement":
        #     self.list_studio_folders(call)
        # elif self.mode == "mailing":
        #     self.get_studio_shared_folders(call)
        # elif self.mode == "enhancement":
        #     self.get_studio_image_settings(call)



    def list_studio_folders(self, call):
        self.write_to_log('list_studio_folders')
        self.current_path = f"{self.base_path}/{self.selected_studio}"
        folders = self.get_folders_list()
        folders_keyboard = self.create_keyboard(folders, folders)
        self.update_message(call, text=self.current_path.replace('/cloud/reflect/files/', ''),
                            keyboard=folders_keyboard)

    def show_next_folder(self, call):
        folders = self.get_folders_list()
        folders_keyboard = self.create_keyboard(folders, folders)
        visible_path = self.current_path.replace('/cloud/reflect/files/', '')
        self.update_message(call, text=visible_path, keyboard=folders_keyboard)

    def get_new_value_from_user(self, call):
        keyboard = InlineKeyboardMarkup()
        home_button = InlineKeyboardButton(text="🏠", callback_data="home_clicked")
        keyboard.add(home_button)
        self.update_message(call, text=f'Текущее значение '
                                       f'{call.data.replace("image_settings/", "")} \n'
                                       f'Чтобы его изменить ответьте на это сообщение с новым значением',
                            keyboard=keyboard)

    def call_index(self, call):
        self.change_ownership()
        visible_path = self.current_path.replace('/cloud/reflect/files/', '')
        self.update_message(call, text="Проверка индексации папки...")
        if self.check_ready_for_index():
            result = self.run_index()
            result = visible_path + '\n' + result
            self.update_message(call, text=result)
        else:
            self.update_message(call, text="Папка недоступна для индексации")

    def check_ready_for_index(self):
        initial_count = self.count_files_in_folder(self.current_path)
        time.sleep(5)
        final_count = self.count_files_in_folder(self.current_path)
        if final_count == initial_count:
            return True

    @staticmethod
    def count_files_in_folder(folder_path):
        count = 0
        for root, dirs, files in os.walk(folder_path):
            count += len(files)
        return count

    def handle_record(self, call):
        record_name = call.data.replace('record', '')
        text = f'Удалить {record_name} из рассылки?'
        keyboard = InlineKeyboardMarkup()
        delete_button = InlineKeyboardButton(text='Удалить', callback_data=f'delete:{call.data}')
        home_button = InlineKeyboardButton(text="🏠", callback_data="home_clicked")
        keyboard.add(delete_button, home_button)
        self.update_message(call, text=text, keyboard=keyboard)

    def delete_record(self, call):
        phone_number = call.data.split(' ')[1]
        self.shared_folders = [folder for folder in self.shared_folders if
                               folder["client_phone_number"] != phone_number]

        self.save_shared_folders()

        if self.shared_folders:
            keyboard = self.create_keyboard([x.get('client_name') + '\n' + x.get('client_phone_number')
                                             for x in self.shared_folders],
                                            ['record' + x.get('client_name') + ' ' +
                                             x.get('client_phone_number')
                                         for x in self.shared_folders])
        else:
            keyboard = InlineKeyboardMarkup()
            home_button = InlineKeyboardButton(text="🏠", callback_data="home_clicked")
            keyboard.add(home_button)
        self.update_message(call, text=f'Рассылка за: {self.mailing_date}', keyboard=keyboard)

    def save_shared_folders(self):
        shared_folder_file = self.selected_studio + "_рассылка.json"
        try:
            with open(os.path.join('/cloud/reflect/files/Рассылка', shared_folder_file), "w") as mailing_file:
                data = {
                    'date': self.mailing_date,
                    'shared_folders': self.shared_folders
                }

                json.dump(data, mailing_file, indent=4)

        except Exception as e:
            self.write_to_log(f'error writing shared folders: {e}')

    @staticmethod
    def create_keyboard(button_labels, callback_data, no_home_btn=False):
        # Calculate the number of rows needed based on the number of buttons
        num_rows = (len(button_labels) + 2) // 3

        keyboard_rows = []

        # Create keyboard rows with 3 buttons per row
        for i in range(num_rows):
            # Calculate the start and end index for each row
            start_index = i * 3
            end_index = min(start_index + 3, len(button_labels))

            row = [InlineKeyboardButton(label, callback_data=data) for label, data in
                   zip(button_labels[start_index:end_index], callback_data[start_index:end_index])]

            keyboard_rows.append(row)

        if not no_home_btn:
            home_button = InlineKeyboardButton(text="🏠", callback_data="home_clicked")
            keyboard_rows[-1].append(home_button)

        keyboard = InlineKeyboardMarkup()
        for row in keyboard_rows:
            keyboard.add(*row)

        return keyboard

    def update_message(self, call, text=None, keyboard=None):

        start_time = time.time()

        args = f'text = {text}, keyboard = {keyboard}'
        # self.bot.send_message(call.message.chat.id, args)
        try:
            if keyboard and not text:
                if keyboard != call.message.reply_markup:
                    self.bot.edit_message_reply_markup(message_id=call.message.message_id, chat_id=call.message.chat.id,
                                                       reply_markup=keyboard)
            elif keyboard and text:
                if not (keyboard == call.message.reply_markup and text == call.message.text):
                    self.bot.edit_message_text(message_id=call.message.message_id, chat_id=call.message.chat.id,
                                               text=text, reply_markup=keyboard)

            elif text and not keyboard:
                if text != call.message.text and text != call.data:
                    self.bot.edit_message_text(message_id=call.message.message_id, chat_id=call.message.chat.id,
                                               text=text, reply_markup=call.message.reply_markup)
        except Exception as e:
            self.write_to_log(e)

        end_time = time.time()
        execution_time = end_time - start_time
        print(f"'update_message' execution time: {execution_time} seconds")

    def get_folders_list(self):

        directory_path = self.current_path
        folders_list = [entry for entry in os.listdir(directory_path)
                        if os.path.isdir(os.path.join(directory_path, entry))]

        return folders_list

    def check_exists_folders_inside(self, message):
        try:
            if any(os.path.isdir(os.path.join(self.current_path, entry)) for entry in os.listdir(self.current_path)):
                return True
        except Exception as e:
            self.bot.send_message(message.chat.id, str(e))

    @staticmethod
    def write_to_log(message):
        with open('/cloud/copy_script/tg_bot.log', 'a+') as log_file:
            log_file.write(str(message) + '\n')

    def get_ai_queue(self):
        if not os.path.exists(os.path.join(os.getcwd(), 'ai_enhance_queue.json')):
            with open(os.path.join(self.base_path, 'ai_enhance_queue.json'), 'w') as f:
                json.dump([], f)
                return []
        with open(os.path.join(os.getcwd(), 'ai_enhance_queue.json'), 'r') as f:
            return json.load(f)

    def add_to_ai_queue(self, folder):
        # sudo_password = environ.get('SUDOP')
        ai_index_queue = self.get_ai_queue()
        if folder in ai_index_queue:
            return
        ai_index_queue.insert(0, folder)
        with open(os.path.join(os.getcwd(), 'ai_enhance_queue.json'), 'w') as f:
            json.dump(ai_index_queue, f)


if __name__ == "__main__":
    bot = TelegramBot()
    bot.start_polling()
