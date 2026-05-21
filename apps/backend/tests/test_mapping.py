"""Unit tests for the mapping service — no LLM, no DB, no network."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from job_copilot_api.schemas.cv_profile import (
    CVProfile,
    JobPreferences,
    PersonalInfo,
    SocialLinks,
    WorkExperience,
    Education,
)
from job_copilot_api.schemas.form_field import FormField
from job_copilot_api.services.mapping import (
    _coerce_value,
    _normalize,
    _resolve,
    _tier_for,
    map_fields,
)


# ──────────────────────────── helpers ────────────────────────────

def make_field(label: str | None = None, name: str | None = None, placeholder: str | None = None) -> FormField:
    return FormField(
        selector=f"#field-{label or name or 'x'}",
        kind="text",
        label=label,
        name=name,
        placeholder=placeholder,
    )


def make_profile(**kw) -> CVProfile:
    return CVProfile(
        personal_info=PersonalInfo(
            first_name="Jane",
            last_name="Doe",
            full_name="Jane Doe",
            email="jane@example.com",
            phone="+1555000000",
            **kw,
        )
    )


# ──────────────────────────── _normalize ─────────────────────────

def test_normalize_strips_and_lowercases():
    assert _normalize("  First  Name  ") == "first name"


def test_normalize_replaces_separators():
    assert _normalize("first_name") == "first name"
    assert _normalize("first-name") == "first name"


def test_normalize_none():
    assert _normalize(None) == ""


# ──────────────────────────── _tier_for ──────────────────────────

@pytest.mark.parametrize("conf,has_value,expected_tier", [
    (0.95, True,  "auto"),
    (0.92, True,  "auto"),
    (0.91, True,  "suggest"),
    (0.80, True,  "suggest"),
    (0.78, True,  "suggest"),
    (0.77, True,  "approve"),
    (0.50, True,  "approve"),
    (0.95, False, "approve"),  # value missing → always approve
    (0.80, False, "approve"),
])
def test_tier_for(conf, has_value, expected_tier):
    tier, _ = _tier_for(conf, has_value)
    assert tier == expected_tier


# ──────────────────────────── _coerce_value ──────────────────────

def test_coerce_bool_true():
    assert _coerce_value(True) == "Yes"


def test_coerce_bool_false():
    assert _coerce_value(False) == "No"


def test_coerce_string_passthrough():
    assert _coerce_value("hello") == "hello"


def test_coerce_httpurl_no_trailing_slash():
    from pydantic import HttpUrl
    url = HttpUrl("https://github.com/janedoe")
    result = _coerce_value(url)
    assert not result.endswith("/"), f"trailing slash in: {result!r}"
    assert "github.com/janedoe" in result


# ──────────────────────────── _resolve ───────────────────────────

def test_resolve_flat_field():
    p = make_profile()
    assert _resolve(p, "personal_info.first_name") == "Jane"


def test_resolve_nested():
    from job_copilot_api.schemas.cv_profile import Address
    p = CVProfile(personal_info=PersonalInfo(address=Address(city="Istanbul")))
    assert _resolve(p, "personal_info.address.city") == "Istanbul"


def test_resolve_list_index():
    p = CVProfile(work_experience=[WorkExperience(company="Acme", title="Dev")])
    assert _resolve(p, "work_experience[0].company") == "Acme"


def test_resolve_out_of_range_index():
    p = CVProfile(work_experience=[WorkExperience(company="X", title="Y")])
    assert _resolve(p, "work_experience[5].company") is None


def test_resolve_missing_path():
    p = make_profile()
    assert _resolve(p, "personal_info.nonexistent_field") is None


def test_resolve_preference_requires_visa():
    p = CVProfile(preferences=JobPreferences(requires_visa_sponsorship=True))
    assert _resolve(p, "preferences.requires_visa_sponsorship") is True


def test_resolve_preference_available_start_date():
    p = CVProfile(preferences=JobPreferences(available_start_date="2026-07-01"))
    assert _resolve(p, "preferences.available_start_date") == "2026-07-01"


# ──────────────────────────── map_fields (fuzzy) ─────────────────

@pytest.mark.asyncio
async def test_map_email_field():
    profile = make_profile()
    fields = [make_field(label="Email Address")]
    with patch("job_copilot_api.services.mapping._llm_map_residuals", new=AsyncMock(return_value=[])):
        mappings = await map_fields(fields, profile)
    assert len(mappings) == 1
    m = mappings[0]
    assert m.json_path == "personal_info.email"
    assert m.value == "jane@example.com"
    assert m.tier == "auto"
    assert m.source == "fuzzy"


@pytest.mark.asyncio
async def test_map_first_name_field():
    profile = make_profile()
    fields = [make_field(label="First Name")]
    with patch("job_copilot_api.services.mapping._llm_map_residuals", new=AsyncMock(return_value=[])):
        mappings = await map_fields(fields, profile)
    assert mappings[0].json_path == "personal_info.first_name"
    assert mappings[0].value == "Jane"


@pytest.mark.asyncio
async def test_map_multiple_fields():
    profile = make_profile()
    fields = [
        make_field(label="Email"),
        make_field(label="Phone Number"),
        make_field(label="LinkedIn"),
    ]
    with patch("job_copilot_api.services.mapping._llm_map_residuals", new=AsyncMock(return_value=[])):
        mappings = await map_fields(fields, profile)
    paths = {m.json_path for m in mappings}
    assert "personal_info.email" in paths
    assert "personal_info.phone" in paths
    assert "social_links.linkedin" in paths


@pytest.mark.asyncio
async def test_map_unknown_field_becomes_skip():
    profile = make_profile()
    fields = [make_field(label="xyzzy-not-a-real-field-qwerty")]

    from job_copilot_api.schemas.mapping import FieldMapping
    skip_mapping = FieldMapping(
        selector=fields[0].selector,
        json_path=None,
        value=None,
        confidence=0.0,
        tier="skip",
        source="skip",
        rationale="llm: no match",
    )
    with patch("job_copilot_api.services.mapping._llm_map_residuals", new=AsyncMock(return_value=[skip_mapping])):
        mappings = await map_fields(fields, profile)
    assert mappings[0].tier == "skip"


@pytest.mark.asyncio
async def test_map_fuzzy_match_by_name_attr():
    """Should fuzzy-match even when only the HTML name attribute is provided."""
    profile = make_profile()
    field = FormField(selector="#f", kind="text", name="email", label=None, placeholder=None)
    with patch("job_copilot_api.services.mapping._llm_map_residuals", new=AsyncMock(return_value=[])):
        mappings = await map_fields([field], profile)
    assert mappings[0].json_path == "personal_info.email"


@pytest.mark.asyncio
async def test_map_missing_value_becomes_approve():
    """When profile path is matched but value is missing → tier=approve."""
    profile = CVProfile()  # empty profile — no email
    fields = [make_field(label="Email Address")]
    with patch("job_copilot_api.services.mapping._llm_map_residuals", new=AsyncMock(return_value=[])):
        mappings = await map_fields(fields, profile)
    assert mappings[0].tier == "approve"
    assert mappings[0].value is None


@pytest.mark.asyncio
async def test_map_boolean_coercion():
    """Boolean preferences should be rendered as Yes/No strings."""
    profile = CVProfile(preferences=JobPreferences(willing_to_relocate=True))
    fields = [make_field(label="Willing to Relocate")]
    with patch("job_copilot_api.services.mapping._llm_map_residuals", new=AsyncMock(return_value=[])):
        mappings = await map_fields(fields, profile)
    assert mappings[0].value == "Yes"


@pytest.mark.asyncio
async def test_map_visa_sponsorship_field():
    """requires_visa_sponsorship must be resolvable — was missing from model."""
    profile = CVProfile(preferences=JobPreferences(requires_visa_sponsorship=False))
    fields = [make_field(label="Visa Sponsorship")]
    with patch("job_copilot_api.services.mapping._llm_map_residuals", new=AsyncMock(return_value=[])):
        mappings = await map_fields(fields, profile)
    assert mappings[0].json_path == "preferences.requires_visa_sponsorship"
    assert mappings[0].value == "No"


@pytest.mark.asyncio
async def test_llm_timeout_gracefully_falls_back():
    """If LLM times out, residual fields become skip — fuzzy results still returned."""
    profile = make_profile()
    # One field fuzzy-matches, one doesn't
    fields = [
        make_field(label="Email"),
        make_field(label="xyzzy-unique-unknown-field"),
    ]

    async def slow_llm(*args, **kwargs):
        raise asyncio.TimeoutError()

    with patch("job_copilot_api.services.mapping.call_json", new=slow_llm):
        mappings = await map_fields(fields, profile)

    tiers = {m.json_path: m.tier for m in mappings}
    assert tiers.get("personal_info.email") == "auto"
    skip = next(m for m in mappings if m.json_path is None)
    assert skip.tier == "skip"
