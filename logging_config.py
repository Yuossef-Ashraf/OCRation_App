"""
Logging configuration for OCRATION application.
Provides centralized, production-ready logging with console and rotating file handlers.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional


class UTF8StreamHandler(logging.StreamHandler):
    """
    Custom StreamHandler that safely handles UTF-8 characters
    across different OS environments (particularly Windows command prompts).
    """
    def emit(self, record):
        try:
            msg = self.format(record)
            # Replace unsupported emoji / symbols gracefully if needed
            msg = msg.replace('✓', '[OK]').replace('✗', '[ERROR]').replace('⚠️', '[WARN]')
            stream = self.stream
            stream.write(msg + self.terminator)
            stream.flush()
        except Exception:
            self.handleError(record)


def setup_logging(
    log_level: int = logging.INFO,
    log_dir: str = "logs",
    log_file_name: str = "ocration.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Configure root application logging with console and rotating file handlers.

    Args:
        log_level: Logging level (e.g. logging.INFO, logging.DEBUG)
        log_dir: Directory where log files are stored
        log_file_name: Name of the log file
        max_bytes: Maximum size per log file before rotation
        backup_count: Number of rotated log archives to retain

    Returns:
        logging.Logger: Configured root logger
    """
    # Ensure logs directory exists
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError:
            pass

    logger = logging.getLogger("ocration")
    logger.setLevel(log_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if logger.handlers:
        return logger

    # 1. Console Handler (UTF-8 safe)
    console_handler = UTF8StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 2. Rotating File Handler (UTF-8 encoded)
    try:
        log_file_path = os.path.join(log_dir, log_file_name)
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not initialize file logger: {e}")

    return logger


# Default logger initialization
logger = setup_logging()
