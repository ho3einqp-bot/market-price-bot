import os
import logging
from logging.handlers import RotatingFileHandler
import sys

logger = logging.getLogger("PriceBot")


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colored level names"""
    COLOR_CODES = {
        logging.DEBUG: '\033[1;36m',  # Cyan
        logging.INFO: '\033[1;34m',  # Blue
        logging.WARNING: '\033[1;33m',  # Yellow
        logging.ERROR: '\033[1;31m',  # Red
        logging.CRITICAL: '\033[1;35m'  # Magenta
    }
    RESET_CODE = '\033[0m'

    def format(self, record):
        # Colorize the level name
        original_levelname = record.levelname
        if record.levelno in self.COLOR_CODES:
            colored_level = f"{self.COLOR_CODES[record.levelno]}{original_levelname}{self.RESET_CODE}"
            record.levelname = colored_level
        result = super().format(record)
        record.levelname = original_levelname  # Restore original level name
        return result


def configure_logging():
    log_dir = os.path.dirname("logs/bot.log")
    os.makedirs(log_dir, exist_ok=True)

    logger.setLevel(logging.DEBUG)

    # File handler (same as before)
    file_handler = RotatingFileHandler(
        'logs/bot.log',
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_format = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)

    # Colored console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    console_format = ColoredFormatter(
        '\033[1;32m%(asctime)s\033[0m %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Third-party library logging levels
    logging.getLogger('apscheduler').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
