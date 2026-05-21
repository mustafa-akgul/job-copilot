"""Field → CVProfile-path mapping.

Two stages:
  1. Fuzzy pre-pass via rapidfuzz against a synonym table.
  2. LLM fallback for residual (skip) fields — semantic, grounded to profile paths.
     Capped at LLM_RESIDUAL_TIMEOUT seconds so auto-fills are never blocked.

Returns ``FieldMapping`` per input field with tier (auto/suggest/approve/skip).
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import structlog
from pydantic import HttpUrl as PydanticHttpUrl
from rapidfuzz import fuzz, process

from ..config import settings
from ..schemas import CVProfile, FieldMapping
from ..schemas.form_field import FormField
from .llm import call_json

log = structlog.get_logger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "field_mapping.md"

# LLM residual pass must finish within this budget — auto-fills are not blocked.
_LLM_RESIDUAL_TIMEOUT = 20.0


SYNONYMS: dict[str, str] = {
    "first name": "personal_info.first_name",
    "given name": "personal_info.first_name",
    "last name": "personal_info.last_name",
    "surname": "personal_info.last_name",
    "family name": "personal_info.last_name",
    "full name": "personal_info.full_name",
    "name": "personal_info.full_name",
    "email": "personal_info.email",
    "email address": "personal_info.email",
    "e mail": "personal_info.email",
    "phone": "personal_info.phone",
    "phone number": "personal_info.phone",
    "mobile": "personal_info.phone",
    "mobile number": "personal_info.phone",
    "telephone": "personal_info.phone",
    "city": "personal_info.address.city",
    "state": "personal_info.address.state",
    "country": "personal_info.address.country",
    "postal code": "personal_info.address.postal_code",
    "zip": "personal_info.address.postal_code",
    "zip code": "personal_info.address.postal_code",
    "address": "personal_info.address.street",
    "street address": "personal_info.address.street",
    "linkedin": "social_links.linkedin",
    "linkedin url": "social_links.linkedin",
    "linkedin profile": "social_links.linkedin",
    "github": "social_links.github",
    "github url": "social_links.github",
    "portfolio": "social_links.portfolio",
    "portfolio url": "social_links.portfolio",
    "website": "social_links.website",
    "personal website": "social_links.website",
    "summary": "personal_info.summary",
    "about you": "personal_info.summary",
    "about me": "personal_info.summary",
    "tell us about yourself": "personal_info.summary",
    "headline": "personal_info.headline",
    "professional headline": "personal_info.headline",
    "expected salary": "preferences.expected_salary",
    "salary expectation": "preferences.expected_salary",
    "desired salary": "preferences.expected_salary",
    "notice period": "preferences.notice_period",
    "available start date": "preferences.available_start_date",
    "start date": "preferences.available_start_date",
    "willing to relocate": "preferences.willing_to_relocate",
    "open to relocation": "preferences.willing_to_relocate",
    "work authorization": "preferences.work_authorization",
    "authorized to work": "preferences.work_authorization",
    "visa sponsorship": "preferences.requires_visa_sponsorship",
    "require visa sponsorship": "preferences.requires_visa_sponsorship",
    "requires sponsorship": "preferences.requires_visa_sponsorship",
    "preferred work mode": "preferences.preferred_work_mode",
    "remote": "preferences.preferred_work_mode",
    "work preference": "preferences.preferred_work_mode",
}


_SEGMENT = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)(?:\[(\d+)\])?")


def _normalize(s: str | None) -> str:
    return " ".join((s or "").lower().replace("_", " ").replace("-", " ").split())


def _coerce_value(v: Any) -> str:
    """Convert Pydantic special types and plain values to clean strings."""
    if isinstance(v, PydanticHttpUrl):
        # Pydantic v2 adds trailing slash to bare domains — strip it.
        return str(v).rstrip("/")
    if isinstance(v, bool):
        return "Yes" if v else "No"
    return str(v)


def _resolve(profile: CVProfile, path: str) -> Any | None:
    cursor: Any = profile
    for match in _SEGMENT.finditer(path):
        attr, idx = match.group(1), match.group(2)
        if cursor is None:
            return None
        cursor = getattr(cursor, attr, None) if hasattr(cursor, attr) else (
            cursor.get(attr) if isinstance(cursor, dict) else None
        )
        if cursor is None:
            return None
        if idx is not None:
            try:
                cursor = cursor[int(idx)]
            except (IndexError, TypeError):
                return None
    return cursor


def _fuzzy_match(label: str | None, threshold: int) -> tuple[str | None, float]:
    norm = _normalize(label)
    if not norm:
        return None, 0.0
    match = process.extractOne(norm, SYNONYMS.keys(), scorer=fuzz.WRatio)
    if not match:
        return None, 0.0
    key, score, _ = match
    if score < threshold:
        return None, score / 100.0
    return SYNONYMS[key], score / 100.0


def _best_candidate(field: FormField, threshold: int) -> tuple[str | None, float]:
    best: tuple[str | None, float] = (None, 0.0)
    for candidate in (field.label, field.name, field.placeholder, field.id):
        if not candidate:
            continue
        path, score = _fuzzy_match(candidate, threshold)
        if path and score > best[1]:
            best = (path, score)
    return best


def _tier_for(confidence: float, has_value: bool) -> tuple[str, str]:
    if not has_value:
        return "approve", "fuzzy"
    if confidence >= 0.92:
        return "auto", "fuzzy"
    if confidence >= 0.78:
        return "suggest", "fuzzy"
    return "approve", "fuzzy"


def _profile_keys(profile: CVProfile) -> list[str]:
    """Flat list of valid profile paths for the LLM to choose from."""
    base = [
        "personal_info.first_name", "personal_info.last_name", "personal_info.full_name",
        "personal_info.email", "personal_info.phone", "personal_info.headline",
        "personal_info.summary", "personal_info.address.city", "personal_info.address.state",
        "personal_info.address.country", "personal_info.address.postal_code",
        "personal_info.address.street",
        "social_links.linkedin", "social_links.github", "social_links.portfolio",
        "social_links.website",
        "preferences.expected_salary", "preferences.notice_period",
        "preferences.available_start_date", "preferences.willing_to_relocate",
        "preferences.work_authorization", "preferences.requires_visa_sponsorship",
        "preferences.preferred_work_mode",
    ]
    for i in range(len(profile.work_experience)):
        base += [f"work_experience[{i}].{k}" for k in ("company", "title", "start_date", "end_date", "description")]
    for i in range(len(profile.education)):
        base += [f"education[{i}].{k}" for k in ("institution", "degree", "field_of_study", "start_date", "end_date", "gpa")]
    for i in range(len(profile.projects)):
        base += [f"projects[{i}].{k}" for k in ("name", "description", "url")]
    return base


def _field_payload(field: FormField) -> dict[str, Any]:
    return {
        "selector": field.selector,
        "kind": field.kind,
        "input_type": field.input_type,
        "label": field.label,
        "name": field.name,
        "placeholder": field.placeholder,
        "required": field.required,
        "options": [o.label for o in field.options[:25]] if field.options else None,
    }


def _skip_mapping(field: FormField, rationale: str) -> FieldMapping:
    return FieldMapping(
        selector=field.selector,
        json_path=None,
        value=None,
        confidence=0.0,
        tier="skip",
        source="skip",
        rationale=rationale,
    )


async def _llm_map_residuals(
    residuals: list[FormField], profile: CVProfile
) -> list[FieldMapping]:
    """LLM pass for fuzzy-unmatched fields, capped at _LLM_RESIDUAL_TIMEOUT seconds."""
    if not residuals:
        return []

    prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    payload = {
        "available_paths": _profile_keys(profile),
        "fields": [_field_payload(f) for f in residuals],
    }

    try:
        data = await call_json(
            prompt,
            json.dumps(payload, ensure_ascii=False),
            timeout=_LLM_RESIDUAL_TIMEOUT,
        )
        raw_rows: list[dict[str, Any]] = data.get("mappings", [])
    except (asyncio.TimeoutError, Exception) as exc:
        log.warning("llm.map.failed", error=str(exc))
        return [_skip_mapping(f, "llm timeout or error") for f in residuals]

    by_selector = {row.get("selector"): row for row in raw_rows}
    mappings: list[FieldMapping] = []
    for f in residuals:
        row = by_selector.get(f.selector, {})
        path: str | None = row.get("json_path")
        confidence = float(row.get("confidence", 0.0))
        rationale: str = row.get("rationale") or "llm"

        if not path:
            mappings.append(_skip_mapping(f, rationale or "llm: no match"))
            continue

        value = _resolve(profile, path)
        tier, _ = _tier_for(confidence, value is not None)
        mappings.append(FieldMapping(
            selector=f.selector,
            json_path=path,
            value=_coerce_value(value) if value is not None else None,
            confidence=confidence,
            tier=tier,  # type: ignore[arg-type]
            source="llm",
            rationale=rationale,
        ))
        log.info("map.llm", selector=f.selector, path=path, confidence=round(confidence, 2), tier=tier)

    return mappings


async def map_fields(fields: list[FormField], profile: CVProfile) -> list[FieldMapping]:
    """Two-stage map: fuzzy pre-pass, then LLM for residuals."""
    threshold = settings.fuzzy_threshold
    mappings: list[FieldMapping] = []
    residuals: list[FormField] = []

    for f in fields:
        path, score = _best_candidate(f, threshold)
        if not path:
            residuals.append(f)
            continue
        value = _resolve(profile, path)
        tier, source = _tier_for(score, value is not None)
        mappings.append(FieldMapping(
            selector=f.selector,
            json_path=path,
            value=_coerce_value(value) if value is not None else None,
            confidence=score,
            tier=tier,  # type: ignore[arg-type]
            source=source,  # type: ignore[arg-type]
            rationale=f"fuzzy score={score:.2f} → {path}",
        ))
        log.info("map.fuzzy", selector=f.selector, path=path, score=round(score, 2), tier=tier)

    llm_mappings = await _llm_map_residuals(residuals, profile)
    mappings.extend(llm_mappings)

    return mappings
