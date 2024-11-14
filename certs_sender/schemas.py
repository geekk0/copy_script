from pydantic import BaseModel


class EmailCertData(BaseModel):
    product_name: str
    number: str
    email: str
    phone: str
    validity_period: str
    date: str
    price: str
    client_name: str


class SendCertData(BaseModel):
    code: str
    date: str
    email: str
    name: str
    number: str
