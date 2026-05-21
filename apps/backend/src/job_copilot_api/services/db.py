"""Async SQLAlchemy store — SQLite locally, Postgres in production.

ProfileRow: one row per (user_id, persona); blob JSON.
ApplicationRow: job application tracking per user.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from threading import RLock

import structlog
from sqlalchemy import JSON, DateTime, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..config import settings
from ..schemas import CVProfile

log = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    pass


class ProfileRow(Base):
    __tablename__ = "profiles"
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    persona: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)


class ApplicationRow(Base):
    __tablename__ = "applications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="applied")
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class EmbeddingRow(Base):
    __tablename__ = "embeddings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    persona: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(JSON, nullable=False)


_engine = create_async_engine(settings.database_url, echo=False, future=True)
_Session: async_sessionmaker[AsyncSession] = async_sessionmaker(_engine, expire_on_commit=False)
_init_lock = RLock()
_initialized = False


async def init_db() -> None:
    global _initialized
    if _initialized:
        return
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    with _init_lock:
        _initialized = True
    log.info("db.init", url=settings.database_url)


class SqliteStore:
    """Implements ProfileStore using SQLAlchemy async."""

    async def get(self, user_id: str, persona: str) -> CVProfile | None:
        async with _Session() as session:
            row = await session.get(ProfileRow, (user_id, persona))
            return CVProfile.model_validate(row.data) if row else None

    async def put(self, user_id: str, profile: CVProfile) -> CVProfile:
        async with _Session() as session:
            existing = await session.get(ProfileRow, (user_id, profile.persona))
            payload = json.loads(profile.model_dump_json())
            if existing:
                existing.data = payload
            else:
                session.add(ProfileRow(user_id=user_id, persona=profile.persona, data=payload))
            await session.commit()
            return profile

    async def list(self, user_id: str) -> list[CVProfile]:
        async with _Session() as session:
            result = await session.execute(select(ProfileRow).where(ProfileRow.user_id == user_id))
            return [CVProfile.model_validate(r.data) for r in result.scalars()]

    async def delete(self, user_id: str, persona: str) -> bool:
        async with _Session() as session:
            row = await session.get(ProfileRow, (user_id, persona))
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True


_store = SqliteStore()


def get_store() -> SqliteStore:
    return _store


# ── Application store ─────────────────────────────────────────────────────────

class ApplicationStore:
    async def create(self, user_id: str, company: str, role: str, url: str | None, notes: str | None) -> ApplicationRow:
        from ..schemas.application import ApplicationRecord  # avoid circular
        row = ApplicationRow(
            id=str(uuid.uuid4()),
            user_id=user_id,
            company=company,
            role=role,
            url=url,
            status="applied",
            filled_at=datetime.now(timezone.utc),
            notes=notes,
        )
        async with _Session() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return row

    async def list(self, user_id: str, limit: int = 50) -> list[ApplicationRow]:
        async with _Session() as session:
            result = await session.execute(
                select(ApplicationRow)
                .where(ApplicationRow.user_id == user_id)
                .order_by(ApplicationRow.filled_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def update(self, user_id: str, app_id: str, status: str | None, notes: str | None) -> ApplicationRow | None:
        async with _Session() as session:
            row = await session.get(ApplicationRow, app_id)
            if not row or row.user_id != user_id:
                return None
            if status is not None:
                row.status = status
            if notes is not None:
                row.notes = notes
            await session.commit()
            await session.refresh(row)
        return row

    async def delete(self, user_id: str, app_id: str) -> bool:
        async with _Session() as session:
            row = await session.get(ApplicationRow, app_id)
            if not row or row.user_id != user_id:
                return False
            await session.delete(row)
            await session.commit()
        return True


_app_store = ApplicationStore()


def get_app_store() -> ApplicationStore:
    return _app_store


# ── Embedding store ───────────────────────────────────────────────────────────

class EmbeddingStore:
    async def upsert(
        self,
        user_id: str,
        persona: str,
        chunks: list[tuple[str, str, list[float]]],
    ) -> None:
        async with _Session() as session:
            # Delete existing chunks for this (user_id, persona) before re-inserting.
            existing = await session.execute(
                select(EmbeddingRow)
                .where(EmbeddingRow.user_id == user_id, EmbeddingRow.persona == persona)
            )
            for row in existing.scalars():
                await session.delete(row)
            for chunk_id, content, embedding in chunks:
                session.add(EmbeddingRow(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    persona=persona,
                    chunk_id=chunk_id,
                    content=content,
                    embedding=embedding,
                ))
            await session.commit()

    async def list(
        self, user_id: str, persona: str
    ) -> list[tuple[str, str, list[float]]]:
        async with _Session() as session:
            result = await session.execute(
                select(EmbeddingRow)
                .where(EmbeddingRow.user_id == user_id, EmbeddingRow.persona == persona)
            )
            return [(r.chunk_id, r.content, r.embedding) for r in result.scalars()]

    async def delete(self, user_id: str, persona: str) -> None:
        async with _Session() as session:
            rows = await session.execute(
                select(EmbeddingRow)
                .where(EmbeddingRow.user_id == user_id, EmbeddingRow.persona == persona)
            )
            for row in rows.scalars():
                await session.delete(row)
            await session.commit()


_embedding_store = EmbeddingStore()


def get_embedding_store() -> EmbeddingStore:
    return _embedding_store
