import os

import telebot
import subprocess

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
        self.bot.message_handler(func=lambda message: True)(self.handle_message)
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_callback_query)

    def start_polling(self):
        self.bot.polling()

    def handle_message(self, message):
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
            keyboard = self.create_keyboard(self.studios, self.studios, no_home_btn=True)
            self.bot.send_message(self.chat_id, "Индексация, выберите студию:", reply_markup=keyboard)
        # else:
        #     self.bot.reply_to(message, "Sorry, I can only handle text messages.")

    def handle_callback_query(self, call):
        if call.message.chat.id != self.chat_id:
            return

        if call.data == "home_clicked":
            keyboard = self.create_keyboard(self.studios, self.studios, no_home_btn=True)
            self.update_message(call, text='Индексация, выберите студию:', keyboard=keyboard)

        elif call.data in self.studios:
            self.selected_studio = call.data
            self.current_path = f"{self.base_path}/{self.selected_studio}"
            folders = self.get_folders_list()
            folders_keyboard = self.create_keyboard(folders, folders)
            self.update_message(call, keyboard=folders_keyboard)

        else:
            if call.data not in self.current_path:
                self.current_path += f"/{call.data}"
            if self.check_exists_folders_inside():
                folders = self.get_folders_list()
                folders_keyboard = self.create_keyboard(folders, folders)
                visible_path = self.current_path.replace('/cloud/reflect/files/', '')
                self.update_message(call, text=visible_path, keyboard=folders_keyboard)

            else:
                visible_path = self.current_path.replace('/cloud/reflect/files/', '')
                result = self.run_index()
                result = visible_path + '\n' + result
                self.update_message(call, text=result)

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

    def check_exists_folders_inside(self):
        try:
            if any(os.path.isdir(os.path.join(self.current_path, entry)) for entry in os.listdir(self.current_path)):
                return True
        except Exception as e:
            self.bot.send_message(e)

    @staticmethod
    def write_to_log(message):
        with open('/cloud/copy_script/tg_bot.log', 'a+') as log_file:
            log_file.write(str(message) + '\n')


if __name__ == "__main__":
    bot = TelegramBot()
    bot.start_polling()
