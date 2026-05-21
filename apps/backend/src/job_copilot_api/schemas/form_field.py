"""Shape of one form field as discovered by the extension's content script."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

FieldKind = Literal["text", "textarea", "select", "checkbox", "radio", "file", "contenteditable"]


class SelectOption(BaseModel):
    value: str
    label: str


class FormField(BaseModel):
    selector: str
    kind: FieldKind
    input_type: Optional[str] = None
    name: Optional[str] = None
    id: Optional[str] = None
    label: Optional[str] = None
    placeholder: Optional[str] = None
    required: bool = False
    options: list[SelectOption] = Field(default_factory=list)
    group: Optional[str] = None
    value: Optional[str] = None
