"""Profile store facade — backed by SQLite today, Postgres tomorrow.

The whole module is async now. Routes ``await`` everything.
"""

from __future__ import annotations

from typing import Protocol

from ..schemas import CVProfile
from .db import SqliteStore, get_store as _get_store


class ProfileStore(Protocol):
    async def get(self, user_id: str, persona: str) -> CVProfile | None: ...
    async def put(self, user_id: str, profile: CVProfile) -> CVProfile: ...
    async def list(self, user_id: str) -> list[CVProfile]: ...
    async def delete(self, user_id: str, persona: str) -> bool: ...


def get_store() -> ProfileStore:
    return _get_store()


__all__ = ["ProfileStore", "SqliteStore", "get_store"]
