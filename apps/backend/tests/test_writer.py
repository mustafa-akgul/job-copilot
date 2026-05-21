"""Tests for AI writing (cover letter) endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from .conftest import AUTH, MINIMAL_PROFILE

JD_TEXT = "We are hiring a Senior Python Developer with 3+ years FastAPI experience."

_WRITER_PERSONA = "writer-test-persona"


def _seed(authed_client):
    profile = {**MINIMAL_PROFILE, "persona": _WRITER_PERSONA}
    r = authed_client.put(f"/api/v1/profiles/{_WRITER_PERSONA}", json=profile)
    assert r.status_code == 200


class TestWriter:
    def test_generate_cover_letter(self, authed_client):
        _seed(authed_client)
        mock_response = {
            "content": "Dear Hiring Manager,\n\nI am excited to apply for this role...",
            "word_count": 42,
        }
        with patch(
            "job_copilot_api.services.writer.call_json",
            new=AsyncMock(return_value=mock_response),
        ):
            r = authed_client.post(
                "/api/v1/ai/generate",
                json={"persona": _WRITER_PERSONA, "jd_text": JD_TEXT},
            )
        assert r.status_code == 200
        body = r.json()
        assert "content" in body
        assert "word_count" in body
        assert body["content"] != ""

    def test_generate_respects_tone(self, authed_client):
        _seed(authed_client)
        mock_response = {"content": "Concise letter.", "word_count": 2}
        with patch(
            "job_copilot_api.services.writer.call_json",
            new=AsyncMock(return_value=mock_response),
        ):
            r = authed_client.post(
                "/api/v1/ai/generate",
                json={"persona": _WRITER_PERSONA, "jd_text": JD_TEXT, "tone": "concise"},
            )
        assert r.status_code == 200

    def test_generate_missing_profile_returns_404(self, authed_client):
        r = authed_client.post(
            "/api/v1/ai/generate",
            json={"persona": "nonexistent-xyz", "jd_text": JD_TEXT},
        )
        assert r.status_code == 404

    def test_short_jd_text_rejected(self, authed_client):
        r = authed_client.post(
            "/api/v1/ai/generate",
            json={"persona": "default", "jd_text": "hi"},
        )
        assert r.status_code == 422

    def test_no_auth_returns_401(self, client):
        r = client.post(
            "/api/v1/ai/generate",
            json={"persona": "default", "jd_text": JD_TEXT},
        )
        assert r.status_code == 401
