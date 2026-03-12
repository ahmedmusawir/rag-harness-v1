from __future__ import annotations

import importlib
import sys

import pytest


MODULE_NAME = "src.services.config_service"


def reload_config_service(monkeypatch: pytest.MonkeyPatch, **env: str):
    for key in [
        "GEMINI_API_KEY",
        "API_HOST",
        "API_PORT",
        "MAX_FILE_SIZE_MB",
        "UPLOAD_TIMEOUT_SECONDS",
        "SUMMARY_REQUIRED",
        "LOG_LEVEL",
        "API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    sys.modules.pop(MODULE_NAME, None)
    return importlib.import_module(MODULE_NAME)


def test_loads_required_and_default_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    module = reload_config_service(monkeypatch, GEMINI_API_KEY="test-key")

    assert module.GEMINI_API_KEY == "test-key"
    assert module.API_HOST == "127.0.0.1"
    assert module.API_PORT == 8000
    assert module.MAX_FILE_SIZE_MB == 50
    assert module.UPLOAD_TIMEOUT_SECONDS == 90
    assert module.SUMMARY_REQUIRED is True
    assert module.LOG_LEVEL == "info"
    assert module.API_KEY == ""
    assert module.API_BASE_URL == "http://127.0.0.1:8000"


def test_raises_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    sys.modules.pop(MODULE_NAME, None)
    monkeypatch.setenv("GEMINI_API_KEY", "")

    with pytest.raises(EnvironmentError, match="GEMINI_API_KEY"):
        importlib.import_module(MODULE_NAME)


def test_parses_custom_values(monkeypatch: pytest.MonkeyPatch) -> None:
    module = reload_config_service(
        monkeypatch,
        GEMINI_API_KEY="live-key",
        API_HOST="0.0.0.0",
        API_PORT="9000",
        MAX_FILE_SIZE_MB="25",
        UPLOAD_TIMEOUT_SECONDS="120",
        SUMMARY_REQUIRED="false",
        LOG_LEVEL="debug",
        API_KEY="secret",
    )

    assert module.API_HOST == "0.0.0.0"
    assert module.API_PORT == 9000
    assert module.MAX_FILE_SIZE_MB == 25
    assert module.UPLOAD_TIMEOUT_SECONDS == 120
    assert module.SUMMARY_REQUIRED is False
    assert module.LOG_LEVEL == "debug"
    assert module.API_KEY == "secret"
    assert module.API_BASE_URL == "http://0.0.0.0:9000"
