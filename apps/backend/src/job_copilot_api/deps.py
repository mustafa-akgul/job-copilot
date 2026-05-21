"""FastAPI dependencies."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from .config import settings
from .services.store import ProfileStore, get_store


async def require_user(authorization: str | None = Header(default=None)) -> str:
    """Verify the bearer token and return the user_id.

    Resolution order:
    1. If SUPABASE_JWT_SECRET is configured → verify as Supabase JWT (production).
    2. Otherwise compare against DEV_TOKEN (local dev / pytest).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()

    if settings.supabase_jwt_secret:
        from .services.auth import verify_token
        return verify_token(token)

    if token == settings.dev_token:
        return "dev-user"

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


def store_dep() -> ProfileStore:
    return get_store()
