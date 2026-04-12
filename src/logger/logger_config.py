import logging
import pathlib
from logging.handlers import TimedRotatingFileHandler
import time

from src.config import Config

BASE_DIR = pathlib.Path(__file__).resolve().parents[2]
logs_dir = BASE_DIR / "logs"


def configure_logging():
    config = Config()
    logs_dir.mkdir(parents=True, exist_ok=True)

    dev = bool(config.get_optional("dev"))

    level = logging.INFO if not dev else logging.DEBUG

    log_filepath = logs_dir / "forwardtest.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
    )

    formatter.converter = time.gmtime

    file_handler = TimedRotatingFileHandler(
        log_filepath, when="midnight", backupCount=30, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    if root_logger.handlers:
        root_logger.handlers.clear()

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
