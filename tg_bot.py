import telebot

from os import environ


class TelegramBot:
    bot = telebot.TeleBot(token=environ.get('BOT_TOKEN'))
    chat_id = environ.get('REFLECT_GROUP_CHAT_ID')

    def notify_admin_folder_ready(self, folder, download_url):
        message = f'Папка {folder} доступна для скачивания по ссылке: {download_url}'
        self.bot.send_message(self.chat_id, message)

    def send_message(self, message):
        self.bot.send_message(self.chat_id, message)
