"""JD analysis — extract requirements and compute profile match score."""

from __future__ import annotations

import structlog

from ..schemas.cv_profile import CVProfile
from ..schemas.jd import JDAnalysis
from .llm import call_json

log = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """\
You are a job description parser. Extract structured data from the job description.

Return a JSON object with exactly these keys:
- required_skills: list[str] — explicitly required skills / technologies (max 20)
- nice_to_have: list[str] — preferred/bonus skills (max 10)
- keywords: list[str] — important ATS keywords (max 15, no duplicates with required_skills)
- experience_required: str | null — e.g. "3–5 years" or null if unspecified
- summary: str — one sentence, max 120 chars

Return ONLY valid JSON, no markdown fences.\
"""


def _normalise(lst: object) -> list[str]:
    if not isinstance(lst, list):
        return []
    return [str(s).strip() for s in lst if s]


def _compute_match(required: list[str], profile: CVProfile) -> tuple[list[str], list[str], int]:
    user_skills = {
        s.lower()
        for s in (
            profile.skills.technical
            + profile.skills.frameworks
            + profile.skills.tools
            + profile.skills.soft
        )
    }
    matching, missing = [], []
    for skill in required:
        sl = skill.lower()
        if any(sl in us or us in sl for us in user_skills):
            matching.append(skill)
        else:
            missing.append(skill)
    score = int(len(matching) / len(required) * 100) if required else 100
    return matching, missing, score


async def analyze_jd(jd_text: str, profile: CVProfile | None = None) -> JDAnalysis:
    result = await call_json(_SYSTEM_PROMPT, jd_text[:4000], timeout=30)

    required = _normalise(result.get("required_skills"))
    nice = _normalise(result.get("nice_to_have"))
    keywords = _normalise(result.get("keywords"))
    experience = result.get("experience_required")
    summary = str(result.get("summary", ""))[:200]

    if profile:
        matching, missing, score = _compute_match(required, profile)
    else:
        matching, missing, score = [], required[:], 0

    log.info("jd.analyzed", required=len(required), match_score=score)

    return JDAnalysis(
        required_skills=required,
        nice_to_have=nice,
        keywords=keywords,
        match_score=score,
        matching_skills=matching,
        missing_skills=missing,
        experience_required=str(experience) if experience else None,
        summary=summary,
    )
