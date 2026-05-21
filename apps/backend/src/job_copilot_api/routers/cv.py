"""CV upload + parse — real implementation."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from ..deps import require_user, store_dep
from ..schemas import CVProfile
from ..services.cv_parser import extract_text, parse_cv
from ..services.store import ProfileStore

router = APIRouter()

_MAX_CV_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/parse", response_model=CVProfile)
async def parse_cv_endpoint(
    file: UploadFile,
    persona: str = "default",
    user_id: str = Depends(require_user),
    store: ProfileStore = Depends(store_dep),
) -> CVProfile:
    suffix = Path(file.filename or "cv").suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type '{suffix}'. Use PDF, DOCX, TXT, or MD.",
        )

    content = await file.read()
    if len(content) > _MAX_CV_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File too large ({len(content) // 1024} KB). Maximum is 10 MB.",
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        text = extract_text(tmp_path)
        if not text.strip():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Could not extract any text from the file.",
            )
        profile = await parse_cv(text, persona=persona)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"CV parsing failed: {type(exc).__name__}: {exc}",
        ) from exc
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    return await store.put(user_id, profile)
