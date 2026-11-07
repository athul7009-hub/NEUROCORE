
import logging

from logging.handlers import RotatingFileHandler

from app.core.logger import get_logger, LOG_FILE


def test_logger_writes_to_file():
    test_logger = get_logger("test_file_logger")

    test_logger.info("NEUROCORE logging test")

    for handler in test_logger.handlers:
        handler.flush()

    assert LOG_FILE.exists()
    assert "NEUROCORE logging test" in LOG_FILE.read_text(
        encoding="utf-8"
    )


def test_logger_prevents_duplicate_handlers():
    test_logger = get_logger("test_duplicate_logger")

    initial_count = len(test_logger.handlers)

    get_logger("test_duplicate_logger")

    assert len(test_logger.handlers) == initial_count


def test_logger_uses_rotating_file_handler():
    test_logger = get_logger("test_rotation_logger")

    assert any(
        isinstance(handler, RotatingFileHandler)
        for handler in test_logger.handlers
    )


def test_logger_uses_configured_log_level():
    test_logger = get_logger("test_level_logger")

    assert test_logger.level == logging.INFO
