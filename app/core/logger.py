
import logging
from logging.handlers import RotatingFileHandler

from app.core.config import PROJECT_ROOT, settings


# Create the logs directory if it doesn't exist
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "neurocore.log"


def get_logger(name: str = "NEUROCORE") -> logging.Logger:
    """
    Create and return a configured application logger.
    """

    logger = logging.getLogger(name)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    log_level = getattr(
        logging,
        settings.log_level.upper(),
        logging.INFO
    )

    logger.setLevel(log_level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # Write logs to a rotating local file
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )

    file_handler.setFormatter(formatter)

    # Also display logs in the terminal
    console_handler = logging.StreamHandler()

    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Shared application logger
logger = get_logger()
