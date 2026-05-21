"""CRUD over saved CV profiles (per persona) — async."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ..deps import require_user, store_dep
from ..schemas import CVProfile
from ..services.store import ProfileStore

router = APIRouter()


class RelevantSection(BaseModel):
    content: str


@router.get("", response_model=list[CVProfile])
async def list_profiles(
    user_id: str = Depends(require_user),
    store: ProfileStore = Depends(store_dep),
) -> list[CVProfile]:
    return await store.list(user_id)


@router.get("/{persona}", response_model=CVProfile)
async def get_profile(
    persona: str,
    user_id: str = Depends(require_user),
    store: ProfileStore = Depends(store_dep),
) -> CVProfile:
    profile = await store.get(user_id, persona)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No profile for persona '{persona}'")
    return profile


@router.put("/{persona}", response_model=CVProfile)
async def put_profile(
    persona: str,
    profile: CVProfile,
    user_id: str = Depends(require_user),
    store: ProfileStore = Depends(store_dep),
) -> CVProfile:
    if profile.persona != persona:
        profile = profile.model_copy(update={"persona": persona})
    saved = await store.put(user_id, profile)
    # Fire-and-forget embedding computation (non-blocking).
    asyncio.create_task(_embed_bg(user_id, persona, saved))
    return saved


@router.delete("/{persona}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    persona: str,
    user_id: str = Depends(require_user),
    store: ProfileStore = Depends(store_dep),
) -> None:
    if not await store.delete(user_id, persona):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # Clean up embeddings for deleted persona.
    try:
        from ..services.db import get_embedding_store
        await get_embedding_store().delete(user_id, persona)
    except Exception:
        pass


@router.get("/{persona}/relevant", response_model=list[RelevantSection])
async def get_relevant_sections(
    persona: str,
    query: str = Query(..., min_length=3),
    top_k: int = Query(5, ge=1, le=20),
    user_id: str = Depends(require_user),
    store: ProfileStore = Depends(store_dep),
) -> list[RelevantSection]:
    profile = await store.get(user_id, persona)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No profile for persona '{persona}'")

    from ..services.embeddings import search_profile, store_profile_embeddings
    from ..services.db import get_embedding_store

    # Compute embeddings on demand if not yet stored.
    existing = await get_embedding_store().list(user_id, persona)
    if not existing:
        await store_profile_embeddings(user_id, persona, profile)

    chunks = await search_profile(user_id, persona, query, top_k=top_k)
    return [RelevantSection(content=c) for c in chunks]


async def _embed_bg(user_id: str, persona: str, profile: CVProfile) -> None:
    try:
        from ..services.embeddings import store_profile_embeddings
        await store_profile_embeddings(user_id, persona, profile)
    except Exception:
        pass
