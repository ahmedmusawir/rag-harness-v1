from __future__ import annotations

import requests

from src.services.config_service import API_BASE_URL


def get(path: str, **kwargs: object) -> requests.Response:
    return requests.get(f"{API_BASE_URL}{path}", timeout=10, **kwargs)


def post(path: str, **kwargs: object) -> requests.Response:
    return requests.post(f"{API_BASE_URL}{path}", timeout=120, **kwargs)


def delete(path: str, **kwargs: object) -> requests.Response:
    return requests.delete(f"{API_BASE_URL}{path}", timeout=30, **kwargs)
