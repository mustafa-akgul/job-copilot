"""Application tracking schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

ApplicationStatus = Literal[
    "applied", "screening", "interview", "offer", "rejected", "withdrawn"
]


class ApplicationCreate(BaseModel):
    company: str = Field(..., min_length=1, max_length=200)
    role: str = Field(..., min_length=1, max_length=200)
    url: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = Field(None, max_length=2000)


class ApplicationUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None
    notes: Optional[str] = Field(None, max_length=2000)


class ApplicationRecord(BaseModel):
    id: str
    company: str
    role: str
    url: Optional[str] = None
    status: ApplicationStatus = "applied"
    filled_at: datetime
    notes: Optional[str] = None
