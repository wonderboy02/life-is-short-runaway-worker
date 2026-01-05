"""
Logging utilities for Runway Worker
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_logger(log_dir: str, worker_id: str, log_level: int = logging.INFO) -> logging.Logger:
    """
    Setup logger with file and console handlers

    Args:
        log_dir: Directory to save log files
        worker_id: Worker ID for log filename
        log_level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    # Create log directory
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger(worker_id)
    logger.setLevel(log_level)

    # Clear existing handlers
    logger.handlers.clear()

    # File handler
    log_filename = f"{worker_id}_{datetime.now().strftime('%Y%m%d')}.log"
    log_path = Path(log_dir) / log_filename

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def log_task_start(logger: logging.Logger, item_id: str, group_id: str):
    """Log task start"""
    logger.info("─" * 60)
    logger.info(f"📋 Task Started: {item_id} (group: {group_id})")
    logger.info("─" * 60)


def log_task_complete(logger: logging.Logger, item_id: str, status: str):
    """Log task completion"""
    emoji = "✅" if status == "SUCCESS" else "❌"
    logger.info(f"{emoji} Task Complete: {item_id} ({status})")
    logger.info("─" * 60)
    logger.info("")


def log_step(logger: logging.Logger, step: int, message: str):
    """Log processing step"""
    logger.info(f"[STEP {step}/6] {message}")


def log_error(logger: logging.Logger, message: str, exception: Exception):
    """Log error with exception details"""
    logger.error(f"❌ {message}")
    logger.error(f"Exception: {type(exception).__name__}: {str(exception)}")
