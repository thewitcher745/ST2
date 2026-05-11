import logging
import pathlib
from logging.handlers import TimedRotatingFileHandler
import time

from src.config import Config

config = Config()

BASE_DIR = pathlib.Path(__file__).resolve().parents[2]
logs_dir = BASE_DIR / "logs"


def configure_logging(is_backtest: bool = False, run_id: str = config.run_id):
    """
    Configures the logging directory. Nests the files by a "backtest" subfolder
    if the related argument is set.
    """

    logs_dir.mkdir(parents=True, exist_ok=True)

    dev = config.dev

    level = logging.INFO if not dev else logging.DEBUG

    log_filepath = logs_dir / run_id / "forwardtest.log"
    if is_backtest:
        log_filepath = logs_dir / "backtest" / run_id / "backtest.log"

    log_filepath.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
    )

    formatter.converter = time.gmtime
    if not is_backtest:
        file_handler = TimedRotatingFileHandler(
            log_filepath, when="midnight", backupCount=30, encoding="utf-8"
        )
    else:
        file_handler = logging.FileHandler(log_filepath, encoding="utf-8")
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
