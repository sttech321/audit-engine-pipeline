"""
Centralized logging configuration.
"""
import logging
import sys
from app.config import get_settings


def setup_logging() -> logging.Logger:
    """Configure and return the application logger."""
    settings = get_settings()
    
    # Create logger
    logger = logging.getLogger("pass97")
    logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Formatter
    formatter = logging.Formatter(settings.log_format)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger


# Module-level logger instance
logger = setup_logging()
