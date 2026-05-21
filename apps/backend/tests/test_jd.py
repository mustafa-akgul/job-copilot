"""Tests for JD analysis endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from .conftest import AUTH, MINIMAL_PROFILE


JD_TEXT = """\
We are looking for a Senior Python Developer with 3+ years of experience.
Requirements: Python, FastAPI, PostgreSQL, Docker, AWS.
Nice to have: Kubernetes, Redis, TypeScript.
"""

# Dedicated persona so other tests can't clobber the profile.
_JD_PERSONA = "jd-test-persona"


def _seed_jd_profile(authed_client):
    profile = {**MINIMAL_PROFILE, "persona": _JD_PERSONA}
    r = authed_client.put(f"/api/v1/profiles/{_JD_PERSONA}", json=profile)
    assert r.status_code == 200


class TestJDAnalyze:
    def test_analyze_mocked_llm(self, authed_client):
        _seed_jd_profile(authed_client)
        mock_response = {
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "nice_to_have": ["Kubernetes"],
            "keywords": ["backend", "API"],
            "experience_required": "3+ years",
            "summary": "Senior Python Developer role at a tech startup",
        }
        with patch(
            "job_copilot_api.services.jd_analyzer.call_json",
            new=AsyncMock(return_value=mock_response),
        ):
            r = authed_client.post(
                "/api/v1/jd/analyze",
                json={"jd_text": JD_TEXT, "persona": _JD_PERSONA},
            )
        assert r.status_code == 200
        body = r.json()
        assert "required_skills" in body
        assert "match_score" in body
        assert 0 <= body["match_score"] <= 100
        assert isinstance(body["matching_skills"], list)
        assert isinstance(body["missing_skills"], list)

    def test_match_score_with_profile(self, authed_client):
        _seed_jd_profile(authed_client)
        mock_response = {
            "required_skills": ["Python", "FastAPI"],
            "nice_to_have": [],
            "keywords": [],
            "experience_required": None,
            "summary": "Role",
        }
        with patch(
            "job_copilot_api.services.jd_analyzer.call_json",
            new=AsyncMock(return_value=mock_response),
        ):
            r = authed_client.post(
                "/api/v1/jd/analyze",
                json={"jd_text": JD_TEXT, "persona": _JD_PERSONA},
            )
        body = r.json()
        # Profile has Python and FastAPI — expect non-zero match score.
        assert body["match_score"] > 0
        assert len(body["matching_skills"]) > 0

    def test_analyze_no_profile_still_works(self, authed_client):
        mock_response = {
            "required_skills": ["Go"],
            "nice_to_have": [],
            "keywords": [],
            "experience_required": "2 years",
            "summary": "Go developer",
        }
        with patch(
            "job_copilot_api.services.jd_analyzer.call_json",
            new=AsyncMock(return_value=mock_response),
        ):
            r = authed_client.post(
                "/api/v1/jd/analyze",
                json={"jd_text": JD_TEXT, "persona": "nonexistent-xyz-123"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["match_score"] == 0
        assert "Go" in body["missing_skills"]

    def test_short_jd_text_rejected(self, authed_client):
        r = authed_client.post(
            "/api/v1/jd/analyze",
            json={"jd_text": "hi", "persona": "default"},
        )
        assert r.status_code == 422

    def test_no_auth_returns_401(self, client):
        r = client.post("/api/v1/jd/analyze", json={"jd_text": JD_TEXT})
        assert r.status_code == 401
