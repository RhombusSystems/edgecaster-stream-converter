"""Logging configuration for EdgeCaster."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

LOGGERS = {
    "edgecaster": "app.log",
    "edgecaster.stream_manager": "stream_manager.log",
    "edgecaster.rhombus_api": "rhombus_api.log",
}

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_dir: Path, dev_mode: bool = False) -> None:
    """Configure application logging with file and optional console handlers."""
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    for logger_name, filename in LOGGERS.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG if dev_mode else logging.INFO)
        logger.handlers.clear()

        if not dev_mode:
            log_file = log_dir / filename
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=10_000_000, backupCount=5
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.INFO)
            logger.addHandler(file_handler)

        if dev_mode:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(logging.DEBUG)
            logger.addHandler(console_handler)
