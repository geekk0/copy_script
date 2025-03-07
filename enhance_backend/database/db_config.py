import os

print(f"sqlite:///{os.path.join(os.path.dirname(__file__), 'main.db')}")

TORTOISE_ORM = {
    "connections": {
        "default": f"sqlite:///{os.path.join(os.path.dirname(__file__), 'main.db')}",
    },
    "apps": {
        "models": {
            "models": ["enhance_backend.models", "aerich.models"],
            "default_connection": "default",
        },
    },
}
