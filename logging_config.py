"""
Logging configuration for OCRATION application.
Provides centralized logging setup for all modules.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


class UTF8StreamHandler(logging.StreamHandler):
    """Custom stream handler that handles UTF-8 encoding properly on Windows."""
    def emit(self, record):
        try:
            msg = self.format(record)
            # Replace emoji/special chars for console output
            msg = msg.replace('✓', '[OK]').replace('✗', '[ERROR]')
            stream = self.stream
            stream.write(msg + self.terminator)
            stream.flush()
        except Exception:
            self.handleError(record)


def setup_logging(log_level=logging.INFO, log_dir="logs"):
    """
    Configure logging for the application.
    
    Args:
        log_level: Logging level (default: logging.INFO)
        log_dir: Directory for log files (default: "logs")
    """
    # Create logs directory if it doesn't exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Console handler with UTF-8 support
    console_handler = UTF8StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation (UTF-8 encoding)
    log_file = os.path.join(log_dir, 'ocration.log')
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'  # Ensure UTF-8 encoding
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger


# Initialize logging when module is imported
setup_logging()
