"""Job description analysis router."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import require_user, store_dep
from ..schemas.jd import JDAnalysis, JDAnalyzeRequest
from ..services.jd_analyzer import analyze_jd
from ..services.store import ProfileStore

router = APIRouter()


@router.post("/analyze", response_model=JDAnalysis)
async def analyze(
    body: JDAnalyzeRequest,
    user_id: str = Depends(require_user),
    store: ProfileStore = Depends(store_dep),
) -> JDAnalysis:
    profile = await store.get(user_id, body.persona)
    return await analyze_jd(body.jd_text, profile)
