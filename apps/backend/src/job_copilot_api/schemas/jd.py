"""Job description analysis schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class JDAnalyzeRequest(BaseModel):
    jd_text: str = Field(..., min_length=10)
    persona: str = "default"


class JDAnalysis(BaseModel):
    required_skills: list[str]
    nice_to_have: list[str]
    keywords: list[str]
    match_score: int = Field(ge=0, le=100)
    matching_skills: list[str]
    missing_skills: list[str]
    experience_required: str | None
    summary: str
