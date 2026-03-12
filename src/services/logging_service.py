from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path

from src.services.config_service import LOG_LEVEL

LOGS_DIR = Path("logs")


def _log_path() -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"


def _configure_root_logger() -> logging.Logger:
    logger = logging.getLogger("managed_rag_api")
    if logger.handlers:
        return logger

    level_name = LOG_LEVEL.upper()
    level = getattr(logging, level_name, logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.setLevel(level)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(_log_path(), encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger


def get_logger(module_name: str | None = None) -> logging.Logger:
    root_logger = _configure_root_logger()
    if not module_name:
        return root_logger
    return root_logger.getChild(module_name)


logger = get_logger(__name__)
