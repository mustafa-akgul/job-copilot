"""Field-to-profile mapping endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import require_user, store_dep
from ..schemas import MapRequest, MapResponse
from ..services.mapping import map_fields
from ..services.store import ProfileStore

router = APIRouter()


@router.post("/map", response_model=MapResponse)
async def map_fields_endpoint(
    payload: MapRequest,
    user_id: str = Depends(require_user),
    store: ProfileStore = Depends(store_dep),
) -> MapResponse:
    profile = await store.get(user_id, payload.persona)
    if profile is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No profile for persona '{payload.persona}'. Upload a CV first.",
        )
    mappings = await map_fields(payload.fields, profile)
    unresolved = [m.selector for m in mappings if m.json_path and m.value is None]
    return MapResponse(mappings=mappings, unresolved=unresolved)
