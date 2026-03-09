from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _get_required_str(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {name}")
    return value


def _get_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped or default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise EnvironmentError(f"Environment variable {name} must be an integer") from exc


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise EnvironmentError(f"Environment variable {name} must be a boolean")


@dataclass
class Config:
    GEMINI_API_KEY: str
    API_HOST: str
    API_PORT: int
    MAX_FILE_SIZE_MB: int
    UPLOAD_TIMEOUT_SECONDS: int
    SUMMARY_REQUIRED: bool
    LOG_LEVEL: str
    API_KEY: str

    @property
    def API_BASE_URL(self) -> str:
        return f"http://{self.API_HOST}:{self.API_PORT}"


def load_settings() -> Config:
    return Config(
        GEMINI_API_KEY=_get_required_str("GEMINI_API_KEY"),
        API_HOST=_get_str("API_HOST", "127.0.0.1"),
        API_PORT=_get_int("API_PORT", 8000),
        MAX_FILE_SIZE_MB=_get_int("MAX_FILE_SIZE_MB", 50),
        UPLOAD_TIMEOUT_SECONDS=_get_int("UPLOAD_TIMEOUT_SECONDS", 90),
        SUMMARY_REQUIRED=_get_bool("SUMMARY_REQUIRED", True),
        LOG_LEVEL=_get_str("LOG_LEVEL", "info").lower(),
        API_KEY=_get_str("API_KEY", ""),
    )


config = load_settings()
SETTINGS = config
GEMINI_API_KEY = config.GEMINI_API_KEY
API_HOST = config.API_HOST
API_PORT = config.API_PORT
MAX_FILE_SIZE_MB = config.MAX_FILE_SIZE_MB
UPLOAD_TIMEOUT_SECONDS = config.UPLOAD_TIMEOUT_SECONDS
SUMMARY_REQUIRED = config.SUMMARY_REQUIRED
LOG_LEVEL = config.LOG_LEVEL
API_KEY = config.API_KEY
API_BASE_URL = config.API_BASE_URL
