"""Personas management — thin metadata wrapper around the profiles store."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..deps import require_user, store_dep
from ..schemas.cv_profile import CVProfile
from ..services.store import ProfileStore

router = APIRouter()


class PersonaMeta(BaseModel):
    persona: str
    display_name: str | None
    skill_count: int
    job_count: int
    education_count: int


class PersonaCloneRequest(BaseModel):
    new_persona: str


def _meta(profile: CVProfile) -> PersonaMeta:
    pi = profile.personal_info
    name = (
        pi.full_name
        or f"{pi.first_name or ''} {pi.last_name or ''}".strip()
        or None
    )
    return PersonaMeta(
        persona=profile.persona,
        display_name=name,
        skill_count=len(profile.skills.technical)
        + len(profile.skills.frameworks)
        + len(profile.skills.tools),
        job_count=len(profile.work_experience),
        education_count=len(profile.education),
    )


@router.get("", response_model=list[PersonaMeta])
async def list_personas(
    user_id: str = Depends(require_user),
    store: ProfileStore = Depends(store_dep),
) -> list[PersonaMeta]:
    profiles = await store.list(user_id)
    return [_meta(p) for p in profiles]


@router.post(
    "/{persona}/clone",
    response_model=CVProfile,
    status_code=status.HTTP_201_CREATED,
)
async def clone_persona(
    persona: str,
    body: PersonaCloneRequest,
    user_id: str = Depends(require_user),
    store: ProfileStore = Depends(store_dep),
) -> CVProfile:
    source = await store.get(user_id, persona)
    if not source:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Persona '{persona}' not found")
    if await store.get(user_id, body.new_persona):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Persona '{body.new_persona}' already exists",
        )
    cloned = source.model_copy(update={"persona": body.new_persona})
    return await store.put(user_id, cloned)
