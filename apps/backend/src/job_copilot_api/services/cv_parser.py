"""CV file → CVProfile pipeline.

extract_text(): PDF/DOCX/TXT → string.
parse_cv(): string → validated CVProfile via the configured LLM.
"""

from __future__ import annotations

from pathlib import Path

import structlog
from pypdf import PdfReader

from ..schemas import CVProfile
from .llm import call_json

log = structlog.get_logger(__name__)


_SYSTEM_PROMPT = """You are a CV/resume parser. Convert the user's raw resume text into a single JSON object matching the CVProfile schema. Output JSON only — no prose, no markdown fences.

Rules:
1. No hallucination. Omit fields not present in the source. Empty arrays for missing list sections.
2. Date normalization: start_date / end_date are strings "YYYY-MM". Year-only → "YYYY-01". Ongoing roles → "PRESENT" and is_current: true where applicable.
3. Always populate first_name, last_name, full_name when a name is given. Single token → first_name + full_name.
4. URLs include scheme (https://). Skip non-URL text.
5. Skills bucketed into technical, tools, frameworks, soft (each is a list of strings).
6. work_experience, education, projects must be sorted most-recent first.
7. schema_version: "1.0", persona: "default" unless told otherwise.

CVProfile schema (abridged):
{
  "schema_version": "1.0",
  "persona": "default",
  "personal_info": {"first_name","last_name","full_name","email","phone","headline","summary",
                    "address":{"street","city","state","postal_code","country"}},
  "social_links": {"linkedin","github","portfolio","website"},
  "education": [{"institution","degree","field_of_study","start_date","end_date","gpa"}],
  "work_experience": [{"company","title","start_date","end_date","is_current","description","technologies"}],
  "projects": [{"name","description","technologies","url"}],
  "skills": {"technical","tools","frameworks","soft"},
  "preferences": {"expected_salary","notice_period","willing_to_relocate","work_authorization","preferred_work_mode"},
  "custom_responses": []
}

Return the JSON object now. The user's CV text follows."""


def extract_text(path: str | Path) -> str:
    """Return plain text. Raises ValueError on unsupported types."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()
    if suffix == ".docx":
        from docx import Document

        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    raise ValueError(f"Unsupported CV format: {suffix}")


_VALID_WORK_AUTH = {"citizen", "permanent_resident", "work_visa", "student_visa", "requires_sponsorship", "other"}
_VALID_WORK_MODE = {"remote", "hybrid", "onsite", "any"}


def _sanitize_raw(raw: dict) -> dict:
    """Fix predictable LLM formatting quirks before Pydantic validation."""
    # URLs: add https:// when scheme is missing
    links = raw.get("social_links") or {}
    for key in ("linkedin", "github", "portfolio", "website"):
        val = links.get(key)
        if isinstance(val, str) and val and not val.startswith(("http://", "https://")):
            links[key] = "https://" + val
    if links:
        raw["social_links"] = links

    # GPA: "3.7/4.0" or "3.7 / 4.0" → 3.7
    for edu in raw.get("education") or []:
        gpa = edu.get("gpa")
        if isinstance(gpa, str):
            edu["gpa"] = float(gpa.split("/")[0].strip()) if gpa.strip() else None

    # Preferences: normalize case-sensitive literals
    prefs = raw.get("preferences") or {}
    if isinstance(prefs.get("preferred_work_mode"), str):
        normalized = prefs["preferred_work_mode"].lower().strip()
        prefs["preferred_work_mode"] = normalized if normalized in _VALID_WORK_MODE else None
    if isinstance(prefs.get("work_authorization"), str):
        normalized = prefs["work_authorization"].lower().strip().replace(" ", "_")
        prefs["work_authorization"] = normalized if normalized in _VALID_WORK_AUTH else "other"
    if prefs:
        raw["preferences"] = prefs

    return raw


async def parse_cv(cv_text: str, persona: str = "default") -> CVProfile:
    """Send text to the LLM, validate against CVProfile, force the persona we want."""
    log.info("cv.parse.start", chars=len(cv_text), persona=persona)
    schema = CVProfile.model_json_schema()
    raw = await call_json(_SYSTEM_PROMPT, cv_text, schema=schema)
    raw["persona"] = persona  # always overwrite — LLMs ignore the rule sometimes
    raw = _sanitize_raw(raw)
    profile = CVProfile.model_validate(raw)
    log.info(
        "cv.parse.done",
        education=len(profile.education),
        work=len(profile.work_experience),
        projects=len(profile.projects),
        skills=len(profile.skills.technical) + len(profile.skills.frameworks),
    )
    return profile
