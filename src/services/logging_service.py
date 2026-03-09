from __future__ import annotations

import logging

from src.services.config_service import LOG_LEVEL


def _configure_logger() -> logging.Logger:
    logger = logging.getLogger("managed_rag_api")
    if logger.handlers:
        return logger

    level_name = LOG_LEVEL.upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )

    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = _configure_logger()
