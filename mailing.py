import os
import json
import time

from yclients_api import YclientsService


class MailingService:
    base_path = "/cloud/reflect/files/Рассылка"
    error = None
    shared_folders = None
    yclients_service = None

    def run(self):
        mailing_files = [f for f in os.listdir(self.base_path) if os.path.isfile(os.path.join(self.base_path, f))
                         and f.lower().endswith('.json')]

        for mailing_file in mailing_files:
            try:
                studio_name = mailing_file.split('_рассылка')[0]
                self.write_to_log(studio_name)
                self.yclients_service = YclientsService(studio_name)
                self.get_shared_folders(mailing_file)
                for shared_folder in self.shared_folders:
                    self.send_notifications_to_client(shared_folder)
                    time.sleep(10)
                os.remove(self.base_path + "/" + mailing_file)
            except Exception as e:
                self.error = f'error run {e}'

    def get_shared_folders(self, mailing_file):
        with open(os.path.join(self.base_path, mailing_file), 'r') as mailing_file:
            self.shared_folders = json.load(mailing_file)['shared_folders']

    def send_notifications_to_client(self, shared_folder):
        try:
            self.yclients_service.send_email_folder_notification_to_client(shared_folder)
        except Exception as e:
            self.error = f'error sending email: {e}'
        time.sleep(20)
        try:
            self.yclients_service.send_whatsapp_folder_notifications_to_client(shared_folder)
        except Exception as e:
            self.error = f'error sending whatsapp: {e}'

    @staticmethod
    def write_to_log(message):
        with open('/cloud/copy_script/mailing.log', 'a+') as log_file:
            log_file.write(str(message) + '\n')
            

if __name__ == '__main__':
    mailing = MailingService()
    mailing.run()
    if mailing.error:
        mailing.write_to_log(mailing.error)
