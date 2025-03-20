import os
from dotenv import load_dotenv
from os import environ
# print(f"sqlite:///{os.path.join(os.path.dirname(__file__), 'main.db')}")
#
# TORTOISE_ORM = {
#     "connections": {
#         "default": f"sqlite:///{os.path.join(os.path.dirname(__file__), 'main.db')}",
#     },
#     "apps": {
#         "models": {
#             "models": ["enhance_backend.models", "aerich.models"],
#             "default_connection": "default",
#         },
#     },
# }

load_dotenv()

DB_USER = environ.get("DB_USER")
DB_PASSWORD = environ.get("DB_PASSWORD")
DB_HOST = environ.get("DB_HOST", "localhost")
DB_PORT = environ.get("DB_PORT", "5432")
DB_NAME = environ.get("DB_NAME", "reflect_backend")

DATABASE_URL = f"postgres://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(DATABASE_URL)
load_dotenv()

TORTOISE_ORM = {
    "connections": {"default": DATABASE_URL},
    "apps": {
        "models": {
            "models": ["enhance_backend.models", "aerich.models"],
            "default_connection": "default",
        }
    },
}