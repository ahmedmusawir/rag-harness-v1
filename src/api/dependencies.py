from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from src.services.config_service import config

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> None:
    if config.API_KEY and api_key != config.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
