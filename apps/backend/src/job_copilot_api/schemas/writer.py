"""AI writing request/response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    persona: str = "default"
    jd_text: str = Field(..., min_length=10)
    tone: Literal["professional", "enthusiastic", "concise"] = "professional"
    max_words: int = Field(300, ge=100, le=600)


class GenerateResponse(BaseModel):
    content: str
    word_count: int
