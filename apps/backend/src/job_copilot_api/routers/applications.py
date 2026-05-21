"""Job application tracking endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import require_user
from ..schemas.application import ApplicationCreate, ApplicationRecord, ApplicationUpdate
from ..services.db import ApplicationStore, get_app_store

router = APIRouter()


def _row_to_record(row) -> ApplicationRecord:
    return ApplicationRecord(
        id=row.id,
        company=row.company,
        role=row.role,
        url=row.url,
        status=row.status,  # type: ignore[arg-type]
        filled_at=row.filled_at,
        notes=row.notes,
    )


def app_store_dep() -> ApplicationStore:
    return get_app_store()


@router.post("", response_model=ApplicationRecord, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate,
    user_id: str = Depends(require_user),
    store: ApplicationStore = Depends(app_store_dep),
) -> ApplicationRecord:
    row = await store.create(
        user_id=user_id,
        company=payload.company,
        role=payload.role,
        url=payload.url,
        notes=payload.notes,
    )
    return _row_to_record(row)


@router.get("", response_model=list[ApplicationRecord])
async def list_applications(
    limit: int = 50,
    user_id: str = Depends(require_user),
    store: ApplicationStore = Depends(app_store_dep),
) -> list[ApplicationRecord]:
    rows = await store.list(user_id, limit=min(limit, 200))
    return [_row_to_record(r) for r in rows]


@router.patch("/{app_id}", response_model=ApplicationRecord)
async def update_application(
    app_id: str,
    payload: ApplicationUpdate,
    user_id: str = Depends(require_user),
    store: ApplicationStore = Depends(app_store_dep),
) -> ApplicationRecord:
    row = await store.update(user_id, app_id, payload.status, payload.notes)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return _row_to_record(row)


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    app_id: str,
    user_id: str = Depends(require_user),
    store: ApplicationStore = Depends(app_store_dep),
) -> None:
    if not await store.delete(user_id, app_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
