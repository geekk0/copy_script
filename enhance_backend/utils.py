import os
import logging

from loguru import logger

log_folder = os.path.join(os.getcwd(), "logs")
if not os.path.exists(log_folder):
    os.makedirs(log_folder)

logger.add(
    os.path.join(log_folder, "enhance_backend.log"),
    format="{time} {level} {message}",
    rotation="10 MB",
    compression="zip",
    level="DEBUG"
)


class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.log(level, record.getMessage())


logging.basicConfig(handlers=[InterceptHandler()], level=0)
for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
    logging.getLogger(logger_name).handlers = [InterceptHandler()]
    logging.getLogger(logger_name).propagate = False