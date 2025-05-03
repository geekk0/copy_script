import os
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