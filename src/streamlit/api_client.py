from __future__ import annotations

import os

import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "").strip()


def _headers(extra_headers: dict[str, str] | None = None) -> dict[str, str]:
    headers = dict(extra_headers or {})
    if API_KEY:
        headers.setdefault("X-API-Key", API_KEY)
    return headers


def _request(method: str, path: str, timeout: int, **kwargs: object) -> requests.Response:
    headers = _headers(kwargs.pop("headers", None))
    try:
        return requests.request(
            method,
            f"{API_BASE_URL}{path}",
            timeout=timeout,
            headers=headers,
            **kwargs,
        )
    except requests.RequestException as exc:
        raise ConnectionError("API unreachable") from exc


def get(path: str, timeout: int = 10, **kwargs: object) -> requests.Response:
    return _request("GET", path, timeout, **kwargs)


def post(path: str, **kwargs: object) -> requests.Response:
    return _request("POST", path, 120, **kwargs)


def delete(path: str, **kwargs: object) -> requests.Response:
    return _request("DELETE", path, 30, **kwargs)
