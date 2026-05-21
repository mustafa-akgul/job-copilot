"""Request/response shapes for POST /api/v1/forms/map."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .form_field import FormField

Tier = Literal["auto", "suggest", "approve", "skip"]


class FieldMapping(BaseModel):
    """A single mapping decision returned to the extension."""

    selector: str
    json_path: Optional[str] = Field(None, description="Dotted path into CVProfile, e.g. 'personal_info.email'")
    value: Optional[Any] = Field(None, description="Resolved value to inject. None means HITL.")
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    tier: Tier = Field(
        "skip",
        description="auto = inject without UI, suggest = show inline, approve = require click, skip = leave blank.",
    )
    source: Literal["fuzzy", "llm", "user", "dummy", "skip"] = "skip"
    rationale: Optional[str] = None


class MapRequest(BaseModel):
    persona: str = "default"
    page_url: Optional[str] = None
    fields: list[FormField]


class MapResponse(BaseModel):
    mappings: list[FieldMapping]
    unresolved: list[str] = Field(default_factory=list, description="Selectors needing human input.")
