import os

import telebot
import subprocess
import pwd
import grp
import json

from os import environ
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

class TelegramBot:
    load_dotenv()
    token = environ.get("BOT_TOKEN")
    bot = telebot.TeleBot(token)
    chat_id = int(environ.get('REFLECT_GROUP_CHAT_ID'))
    studios = ['Силуэт', 'Портрет(ЗАЛ)', 'Reflect Studio']
    current_level_folders = []
    base_path = '/cloud/reflect/files'
    current_path = ''

    def __init__(self):
        self.selected_studio = None
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_callback_query)
        self.bot.message_handler(commands=['start'])(self.handle_start)
        self.shared_folders = []
        self.mailing_date = ''

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
        if message.content_type == 'text':
            keyboard = self.create_keyboard(['Индексация', 'Рассылка'],
                                           ['indexing', 'mailing'], no_home_btn=True)
            if call:
                self.update_message(call, "Выберите действие:", keyboard)
            else:
                self.bot.send_message(message.chat.id, "Выберите действие:", reply_markup=keyboard)

    def handle_callback_query(self, call):

        print(call.data)

        if call.message.chat.id != self.chat_id:
            return

        elif call.data == "home_clicked":
            self.handle_start(call.message, call)

        elif call.data in ["indexing", "mailing"]:
            self.show_studio_select(call)

        elif "mailing:" in call.data or "indexing:" in call.data:
            if call.data.split(":")[1] in self.studios:
                self.show_studio_folders(call)

        elif 'delete:record' in call.data:
            self.delete_record(call)

        elif 'record' in call.data:
            self.handle_record(call)

        else:
            if call.data not in self.current_path:
                self.current_path += f"/{call.data}"
            if self.check_exists_folders_inside(call.message):
                self.show_next_folder(call)
            else:
                self.call_index(call)

    def notify_admin_folder_ready(self, folder, download_url):
        message = f'Папка {folder} доступна для скачивания по ссылке: {download_url}'
        self.bot.send_message(self.chat_id, message)

    def send_message(self, message):
        self.bot.send_message(self.chat_id, message)

    def run_index(self):
        sudo_password = environ.get('SUDOP')
        path = self.current_path.replace('/cloud', '')
        command = f"echo {sudo_password} | sudo -S -u www-data php /var/www/cloud/occ files:scan -p '{path}' --shallow"
        self.current_path = os.path.dirname(self.current_path)
        self.write_to_log(command)
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()

        if process.returncode == 0:
            self.write_to_log(output)
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

    def show_studio_select(self, call):
        if call.data == "indexing":
            text = "Выберите студию для индексации:"
            keyboard = self.create_keyboard(self.studios, ["indexing:" + x for x in self.studios])
        else:
            text = "Выберите студию для управления рассылкой:"
            keyboard = self.create_keyboard(self.studios, ["mailing:" + x for x in self.studios])
        self.update_message(call, text, keyboard)

    def show_studio_folders(self, call):

        self.selected_studio = call.data.split(":")[1]
        if call.data.split(":")[0] == 'indexing':
            self.current_path = f"{self.base_path}/{self.selected_studio}"
            folders = self.get_folders_list()
            folders_keyboard = self.create_keyboard(folders, folders)
            self.update_message(call, text=self.current_path.replace('/cloud/reflect/files/', ''),
                                keyboard=folders_keyboard)
        else:
            self.get_studio_shared_folders(call)

    def show_next_folder(self, call):
        folders = self.get_folders_list()
        folders_keyboard = self.create_keyboard(folders, folders)
        visible_path = self.current_path.replace('/cloud/reflect/files/', '')
        self.update_message(call, text=visible_path, keyboard=folders_keyboard)

    def call_index(self, call):
        self.change_ownership()
        visible_path = self.current_path.replace('/cloud/reflect/files/', '')
        result = self.run_index()
        result = visible_path + '\n' + result
        self.update_message(call, text=result)

    def handle_record(self, call):
        record_name = call.data.replace('record', '')
        text = f'Удалить {record_name} из рассылки?'
        keyboard = InlineKeyboardMarkup()
        delete_button = InlineKeyboardButton(text='Удалить', callback_data=f'delete:{call.data}')
        home_button = InlineKeyboardButton(text="🏠", callback_data="home_clicked")
        keyboard.add(delete_button, home_button)
        self.update_message(call, text=text, keyboard=keyboard)

    def delete_record(self, call):
        print(f'delete record: {call.data}')
        phone_number = call.data.split(' ')[1]
        print(phone_number)
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
                    'data': self.mailing_date,
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


if __name__ == "__main__":
    bot = TelegramBot()
    bot.start_polling()
