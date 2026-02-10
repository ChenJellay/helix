"""FastAPI dependency injection helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from helix.config import settings
from helix.db.session import get_session

# API key security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async for session in get_session():
        yield session


async def verify_api_key(
    api_key: str | None = Security(api_key_header),
) -> str:
    """Verify the API key from the request header.

    In development mode, allows requests without an API key.
    """
    if settings.helix_env == "development":
        return api_key or "dev"

    if not api_key or api_key != settings.helix_api_key:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")

    return api_key
