"""Cover letter and AI writing service."""

from __future__ import annotations

import structlog

from ..schemas.cv_profile import CVProfile
from ..schemas.writer import GenerateResponse
from .llm import call_json

log = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """\
You are an expert career writer. Write a compelling cover letter tailored to the job description.

Rules:
- Never invent experience or skills not present in the candidate profile.
- Open with a strong hook referencing the specific role/company.
- Highlight 2–3 skills or achievements from the profile that directly match the JD.
- Close with a clear call to action.
- Respect the requested tone and word limit.

Return JSON: {"content": "<the cover letter>", "word_count": <integer>}\
"""


def _profile_summary(profile: CVProfile, context_chunks: list[str] | None = None) -> str:
    pi = profile.personal_info
    name = pi.full_name or f"{pi.first_name or ''} {pi.last_name or ''}".strip()

    recent = profile.work_experience[:2]
    jobs_str = "; ".join(f"{w.title} at {w.company}" for w in recent) if recent else "N/A"

    skills_str = ", ".join(
        (profile.skills.technical + profile.skills.frameworks + profile.skills.tools)[:15]
    )

    edu = profile.education[0] if profile.education else None
    edu_str = f"{edu.degree or ''} {edu.field_of_study or ''} — {edu.institution}".strip(" —") if edu else "N/A"

    lines = [
        f"Name: {name}",
        f"Headline: {pi.headline or 'N/A'}",
        f"Summary: {(pi.summary or 'N/A')[:400]}",
        f"Recent roles: {jobs_str}",
        f"Education: {edu_str}",
        f"Skills: {skills_str}",
    ]

    if context_chunks:
        lines.append("Relevant context:\n" + "\n".join(context_chunks[:5]))

    return "\n".join(lines)


async def generate_cover_letter(
    profile: CVProfile,
    jd_text: str,
    tone: str = "professional",
    max_words: int = 300,
    context_chunks: list[str] | None = None,
) -> GenerateResponse:
    user_text = (
        f"CANDIDATE PROFILE:\n{_profile_summary(profile, context_chunks)}\n\n"
        f"JOB DESCRIPTION:\n{jd_text[:3000]}\n\n"
        f"Tone: {tone}\n"
        f"Target length: ~{max_words} words"
    )

    result = await call_json(_SYSTEM_PROMPT, user_text, timeout=45)
    content = str(result.get("content", "")).strip()
    word_count = len(content.split())
    log.info("writer.generated", words=word_count, tone=tone)
    return GenerateResponse(content=content, word_count=word_count)
