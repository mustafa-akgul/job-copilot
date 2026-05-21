"""Embeddings store — chunk CV profiles and index for semantic retrieval.

SQLite stores vectors as JSON blobs; Postgres uses the same JSON path for
portability (pgvector migration is a schema-level swap, not a code change).
"""

from __future__ import annotations

import math
import uuid
from typing import NamedTuple

import structlog

from ..config import settings
from ..schemas.cv_profile import CVProfile

log = structlog.get_logger(__name__)


# ── Chunking ──────────────────────────────────────────────────────────────────

class Chunk(NamedTuple):
    chunk_id: str
    content: str


def chunk_profile(profile: CVProfile) -> list[Chunk]:
    chunks: list[Chunk] = []
    pi = profile.personal_info

    if pi.headline or pi.summary:
        parts = []
        if pi.headline:
            parts.append(pi.headline)
        if pi.summary:
            parts.append(pi.summary)
        chunks.append(Chunk("summary", " ".join(parts)))

    for i, w in enumerate(profile.work_experience):
        desc = w.description or ""
        tech = ", ".join(w.technologies[:10]) if w.technologies else ""
        text = f"{w.title} at {w.company}"
        if w.start_date:
            text += f" ({w.start_date}–{w.end_date or 'present'})"
        if desc:
            text += f": {desc[:400]}"
        if tech:
            text += f" [Tech: {tech}]"
        chunks.append(Chunk(f"work_{i}", text))

    for i, edu in enumerate(profile.education):
        text = f"{edu.degree or ''} {edu.field_of_study or ''} at {edu.institution}".strip()
        chunks.append(Chunk(f"edu_{i}", text))

    for i, proj in enumerate(profile.projects):
        tech = ", ".join(proj.technologies[:8]) if proj.technologies else ""
        text = f"{proj.name}: {proj.description or ''}"
        if tech:
            text += f" [{tech}]"
        chunks.append(Chunk(f"proj_{i}", text[:400]))

    all_skills = (
        profile.skills.technical
        + profile.skills.frameworks
        + profile.skills.tools
        + profile.skills.soft
    )
    if all_skills:
        chunks.append(Chunk("skills", "Skills: " + ", ".join(all_skills[:30])))

    return [c for c in chunks if c.content.strip()]


# ── Embedding calls ───────────────────────────────────────────────────────────

async def _embed_batch(texts: list[str]) -> list[list[float]]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    resp.data.sort(key=lambda d: d.index)
    return [d.embedding for d in resp.data]


# ── Cosine similarity ─────────────────────────────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
    return dot / mag if mag else 0.0


# ── Store operations (delegates to db.py) ────────────────────────────────────

async def store_profile_embeddings(user_id: str, persona: str, profile: CVProfile) -> None:
    if not settings.openai_api_key:
        return
    from .db import get_embedding_store

    chunks = chunk_profile(profile)
    if not chunks:
        return

    texts = [c.content for c in chunks]
    try:
        vectors = await _embed_batch(texts)
    except Exception as exc:
        log.warning("embeddings.failed", error=str(exc))
        return

    store = get_embedding_store()
    await store.upsert(user_id, persona, list(zip([c.chunk_id for c in chunks], texts, vectors)))
    log.info("embeddings.stored", user_id=user_id, persona=persona, chunks=len(chunks))


async def search_profile(user_id: str, persona: str, query: str, top_k: int = 5) -> list[str]:
    if not settings.openai_api_key:
        return []
    from .db import get_embedding_store

    try:
        [query_vec] = await _embed_batch([query])
    except Exception as exc:
        log.warning("embeddings.query_failed", error=str(exc))
        return []

    store = get_embedding_store()
    rows = await store.list(user_id, persona)
    if not rows:
        return []

    scored = sorted(
        ((row[1], _cosine(query_vec, row[2])) for row in rows),
        key=lambda t: t[1],
        reverse=True,
    )
    return [content for content, _ in scored[:top_k]]
