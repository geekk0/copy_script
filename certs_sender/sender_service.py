import imaplib
import email
import smtplib
import time
from os import environ

import fitz
import requests

from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from loguru import logger

import telebot
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from schemas import EmailCertData, SendCertData
from texts import email_subject, email_body

load_dotenv()


class CertsService:
    login = "studio.reflect@yandex.ru"
    username = "Reflect Studio"
    password = environ.get("YANDEX_EMAIL_PSWD")
    imap_server = "imap.yandex.ru"

    def get_certs_data_from_emails(self):
        mail = imaplib.IMAP4_SSL(self.imap_server)
        mail.login(self.login, self.password)

        mail.select("certs_folder")
        sender_filter = "support@yclients.com"
        search_criteria = f'(FROM "{sender_filter}" UNSEEN)'
        status, messages = mail.search(None, search_criteria)

        email_ids = messages[0].split()

        logger.debug(f"email_ids: {email_ids}")

        new_certs = []

        for email_id in email_ids:
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = part.get("Content-Disposition", "")

                if content_type == "text/html" and "attachment" not in content_disposition:

                    html_body = part.get_payload(decode=True)
                    if isinstance(html_body, bytes):
                        html_body = html_body.decode(part.get_content_charset())

                    soup = BeautifulSoup(html_body, 'html.parser')

                    body = soup.find('body')
                    table = body.find('table')
                    tr = table.find('tr')
                    content_td = tr.find_all('td')[1]

                    labels = content_td.find_all('b')
                    contact_labels = content_td.find_all('a')

                    email_cert_data = EmailCertData(
                        product_name=labels[0].find_next_sibling(string=True).strip(),
                        number=self.get_cert_number(msg.get('Subject')),
                        email=contact_labels[1].text.strip(),
                        phone=self.format_phone(contact_labels[0].text.strip()),
                        validity_period=labels[5].find_next_sibling(string=True).strip(),
                        date=labels[3].find_next_sibling(string=True).strip(),
                        price=labels[1].find_next_sibling(string=True).strip(),
                        client_name=labels[2].find_next_sibling(string=True).strip()
                    )

                    new_certs.append(email_cert_data)
        return new_certs

    def enrich_certs_with_codes(
            self,
            certs_list: list[EmailCertData]
    ) -> list[SendCertData]:
        print_certs_list = []
        for cert in certs_list:
            cert_data = self.get_cert_code(cert)
            if cert_data:
                send_cert_data = SendCertData(
                    email=cert.email,
                    name=cert.client_name,
                    phone=cert.phone,
                    code=cert_data.get('code'),
                    date=cert.date.split(' ')[0],
                    number=str(cert_data.get('number'))
                )
                print_certs_list.append(send_cert_data)
        return print_certs_list

    @staticmethod
    def get_cert_number(
            subject: str
    ) -> str:
        decoded_subject = email.header.decode_header(subject)
        decoded_subject = decoded_subject[0][0].decode(decoded_subject[0][1])
        cert_number = decoded_subject.replace("Поступил новый заказ № ", "")
        return cert_number

    @staticmethod
    def format_phone(
            phone_number
    ) -> str:
        phone_number = (phone_number.replace("+", "")
                        .replace(" ", "")
                        .replace("-", ""))

        return phone_number

    @staticmethod
    def get_cert_code(
            cert: EmailCertData
    ) -> dict:
        params = {
            "company_id": "809799",
            "phone": cert.phone
        }

        headers = {
            "Authorization": environ.get("YANDEX_APP_TOKEN"),
            "Accept": "*application/vnd.api.v2+json*"
        }

        response = requests.get(
            url="https://api.yclients.com/api/v1/loyalty/certificates/",
            params=params,
            headers=headers
        )

        print(response.json())
        print(len(response.json()['data']))

        result = None

        if len(response.json()['data']) == 1:

            result = {
                'code': response.json()['data'][0]['number'],
                'number': response.json()['data'][0]['id']
            }

        elif len(response.json()['data']) > 1:

            result = {
                'code': [x['number'] for x in response.json()['data']],
                'number': response.json()['data'][0]['id']
            }

        return result

    def print_certs(self, certs_list: list[SendCertData]):
        for cert in certs_list:
            try:
                if isinstance(cert.code, list):
                    for code in cert.code:
                        self.insert_data_into_cert(code, cert.date)
                else:
                    self.insert_data_into_cert(cert.code, cert.date)
                logger.debug(f'cert for email: {cert.email} was printed')
            except Exception as e:
                logger.error(f'cert for email: {cert.email} was not printed: {e}')

    @staticmethod
    def insert_data_into_cert(code, date):
        input_pdf_path = "cert_original.pdf"
        pdf_document = fitz.open(input_pdf_path)

        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            # page.insert_text((770, 959), cert.number, fontsize=28, color=(0, 0, 0))
            page.insert_text((700, 1055), code, fontsize=28, color=(0, 0, 0))
            page.insert_text((770, 1005), date, fontsize=28, color=(0, 0, 0))
        pdf_document.save(f"files/certificate_{code}.pdf")

    def send_email(self, cert_data, check_email=None):

        smtp_server = self.imap_server.replace('imap', 'smtp')  # assuming same server for SMTP
        smtp_port = 465

        subject = email_subject
        body = email_body
        recipient = cert_data.email
        # recipient = "gekk0dw@gmail.com"

        if check_email:
            recipient = "mufasanw@gmail.com"

        if isinstance(cert_data.code, list):
            pdf_files = []
            for code in cert_data.code:
                pdf_files.append(f"files/certificate_{code}.pdf")
        else:
            pdf_files = [f"files/certificate_{cert_data.code}.pdf"]

        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = self.login
        msg['To'] = recipient

        total_weight = 0
        for file in pdf_files:
            with open(file, 'rb') as f:
                pdf_data = f.read()
                total_weight += len(pdf_data)
            pdf_attachment = MIMEApplication(pdf_data, Name=file)
            pdf_attachment['Content-Disposition'] = 'attachment; filename="%s"' % file
            msg.attach(pdf_attachment)

        msg.attach(MIMEText(body, 'plain'))

        logger.info(f"Attached {len(pdf_files)} files, total weight: {total_weight / (1024 * 1024):.2f} MB")

        try:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            server.login(self.login, self.password)
            server.sendmail(self.login, recipient, msg.as_string())
            server.quit()
            logger.debug(f"Сертификат {cert.number} отправлен")
        except Exception as e:
            cert_service.send_tg_notification(f"Ошибка при отправке сертификата {cert.number}: {e}")
            logger.debug(f"Ошибка при отправке сертификата {cert.number}: {e}")

    @staticmethod
    def send_tg_notification(message):
        token = environ.get("BOT_TOKEN")
        bot = telebot.TeleBot(token)
        chat_id = int(environ.get('REFLECT_GROUP_CHAT_ID'))
        bot.send_message(chat_id=chat_id, text=message)


logger.add(
    f"certs_sender.log",
    format="{time} {level} {message}",
    rotation="10 MB",
    compression='zip',
    level="DEBUG")

while True:
    cert_service = CertsService()
    certs = cert_service.get_certs_data_from_emails()
    # logger.debug(f'certs: {certs}')
    # print_cert_list = cert_service.enrich_certs_with_codes(certs)
    # logger.debug(f'print_cert_list: {print_cert_list}')
    # cert_service.print_certs(print_cert_list)
    #
    # for cert in print_cert_list:
    #     cert_service.send_email(cert)

    time.sleep(60)

