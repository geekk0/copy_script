import imaplib
import email
import smtplib
from os import environ

import fitz
import requests

from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import telebot
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from certs_sender.schemas import EmailCertData, SendCertData
from texts import email_subject, email_body


class CertsService:
    login = "studio.reflect@yandex.ru"
    username = "Reflect Studio"
    password = "zzjzfegjewxmsqad"
    imap_server = "imap.yandex.ru"

    def get_certs_data_from_emails(self):
        mail = imaplib.IMAP4_SSL(self.imap_server)
        mail.login(self.login, self.password)

        mail.select("test_folder")
        sender_filter = "support@yclients.com"
        search_criteria = f'(FROM "{sender_filter} UNSEEN")'
        status, messages = mail.search(None, search_criteria)

        email_ids = messages[0].split()

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
            cert_data = self.get_cert_code(
                cert.phone,
                cert.number
            )
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
            phone: str,
            number: str
    ) -> dict:
        params = {
            "company_id": "809799",
            "phone": phone
        }

        headers = {
            "Authorization": "Bearer 24brpncb9u6rz9fszh3f, "
                             "User a68869f8a94338c802a633c203960539",
            "Accept": "*application/vnd.api.v2+json*"
        }

        response = requests.get(
            url="https://api.yclients.com/api/v1/loyalty/certificates/",
            params=params,
            headers=headers
        )

        result = {
            'code': response.json()['data'][0]['number'],
            'number': response.json()['data'][0]['id']
        }
        return result

    def print_certs(self, certs_list: list[SendCertData]):
        for cert in certs_list:
            input_pdf_path = "cert_original.pdf"

            pdf_document = fitz.open(input_pdf_path)

            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                page.insert_text((770, 959), cert.number, fontsize=28, color=(0, 0, 0))
                page.insert_text((700, 1055), cert.code, fontsize=28, color=(0, 0, 0))
                page.insert_text((770, 1005), cert.date, fontsize=28, color=(0, 0, 0))
            pdf_document.save(f"certificate_{cert.number}.pdf")

    def send_email(self, cert_data, check_email=None):

        smtp_server = self.imap_server.replace('imap', 'smtp')  # assuming same server for SMTP
        smtp_port = 465

        subject = email_subject
        body = email_body
        # recipient = cert_data.email
        recipient = "gekk0dw@gmail.com"

        if check_email:
            recipient = "mufasanw@gmail.com"

        pdf_file = f"certificate_{cert_data.number}.pdf"

        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = self.login
        msg['To'] = recipient

        with open(pdf_file, 'rb') as f:
            pdf_data = f.read()
        pdf_attachment = MIMEApplication(pdf_data, Name=pdf_file)
        pdf_attachment['Content-Disposition'] = 'attachment; filename="%s"' % pdf_file
        msg.attach(pdf_attachment)

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(self.login, self.password)
        server.sendmail(self.login, recipient, msg.as_string())
        server.quit()

    @staticmethod
    def send_tg_notification(message):
        load_dotenv()
        token = environ.get("BOT_TOKEN")
        bot = telebot.TeleBot(token)
        chat_id = int(environ.get('REFLECT_GROUP_CHAT_ID'))
        bot.send_message(chat_id=chat_id, text=message)


cert_service = CertsService()
certs = cert_service.get_certs_data_from_emails()
print_cert_list = cert_service.enrich_certs_with_codes(certs)
cert_service.print_certs(print_cert_list)
for cert in print_cert_list:
    try:
        cert_service.send_email(cert)
        cert_service.send_email(cert, check_email=True)
    except Exception as e:
        cert_service.send_tg_notification(f"Ошибка при отправке сертификата {cert.number}: {e}")

