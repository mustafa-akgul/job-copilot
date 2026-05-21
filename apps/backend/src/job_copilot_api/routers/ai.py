"""AI writing router — cover letter generation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import require_user, store_dep
from ..schemas.writer import GenerateRequest, GenerateResponse
from ..services.store import ProfileStore
from ..services.writer import generate_cover_letter

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    body: GenerateRequest,
    user_id: str = Depends(require_user),
    store: ProfileStore = Depends(store_dep),
) -> GenerateResponse:
    profile = await store.get(user_id, body.persona)
    if not profile:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Profile '{body.persona}' not found — upload your CV first.",
        )

    # Fetch semantically relevant CV sections if embeddings are available.
    context_chunks: list[str] | None = None
    try:
        from ..services.embeddings import search_profile
        context_chunks = await search_profile(user_id, body.persona, body.jd_text[:1000], top_k=5)
    except Exception:
        pass

    return await generate_cover_letter(
        profile=profile,
        jd_text=body.jd_text,
        tone=body.tone,
        max_words=body.max_words,
        context_chunks=context_chunks or None,
    )
