"""
Logging Module
Provides centralized logging configuration for the application
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from .config import config


def setup_logger(name: str = "riftech-security") -> logging.Logger:
    """
    Set up and configure a logger instance
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.logging.level))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    formatter = logging.Formatter(config.logging.format)
    
    # Console handler
    if config.logging.console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler with rotation
    if config.logging.file_enabled:
        log_file = config.paths.logs_dir / f"{name}.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=config.logging.max_file_size,
            backupCount=config.logging.backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Create default logger
logger = setup_logger()
