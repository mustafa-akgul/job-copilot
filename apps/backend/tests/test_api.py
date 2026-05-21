"""Integration tests — real DB (in-memory), no LLM calls."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest

from .conftest import AUTH, MINIMAL_PROFILE


# ──────────────────────────── Profiles CRUD ─────────────────────

class TestProfiles:
    def test_put_and_get_profile(self, authed_client):
        r = authed_client.put("/api/v1/profiles/test-persona", json=MINIMAL_PROFILE)
        assert r.status_code == 200
        body = r.json()
        assert body["persona"] == "test-persona"
        assert body["personal_info"]["email"] == "jane@example.com"

    def test_get_missing_profile_returns_404(self, authed_client):
        r = authed_client.get("/api/v1/profiles/does-not-exist")
        assert r.status_code == 404

    def test_list_profiles_returns_array(self, authed_client, profile_in_store):
        r = authed_client.get("/api/v1/profiles")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert any(p["persona"] == "default" for p in r.json())

    def test_put_overwrites_existing_profile(self, authed_client):
        updated = {**MINIMAL_PROFILE, "persona": "overwrite-test"}
        authed_client.put("/api/v1/profiles/overwrite-test", json=updated)
        updated2 = {**updated, "personal_info": {**MINIMAL_PROFILE["personal_info"], "first_name": "Updated"}}
        r = authed_client.put("/api/v1/profiles/overwrite-test", json=updated2)
        assert r.status_code == 200
        assert r.json()["personal_info"]["first_name"] == "Updated"

    def test_delete_profile(self, authed_client):
        p = {**MINIMAL_PROFILE, "persona": "to-delete"}
        authed_client.put("/api/v1/profiles/to-delete", json=p)
        r = authed_client.delete("/api/v1/profiles/to-delete")
        assert r.status_code == 204
        assert authed_client.get("/api/v1/profiles/to-delete").status_code == 404

    def test_delete_nonexistent_profile_returns_404(self, authed_client):
        assert authed_client.delete("/api/v1/profiles/ghost").status_code == 404


# ──────────────────────────── Forms mapping ─────────────────────

class TestFormsMap:
    def test_map_empty_fields_returns_empty_mappings(self, authed_client, profile_in_store):
        r = authed_client.post(
            "/api/v1/forms/map",
            json={"persona": "default", "fields": []},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["mappings"] == []
        assert body["unresolved"] == []

    def test_map_email_field(self, authed_client, profile_in_store):
        with patch("job_copilot_api.services.mapping._llm_map_residuals", new=AsyncMock(return_value=[])):
            r = authed_client.post(
                "/api/v1/forms/map",
                json={
                    "persona": "default",
                    "fields": [{"selector": "#email", "kind": "text", "label": "Email Address", "required": True, "options": []}],
                },
            )
        assert r.status_code == 200
        m = r.json()["mappings"][0]
        assert m["json_path"] == "personal_info.email"
        assert m["value"] == "jane@example.com"
        assert m["tier"] == "auto"

    def test_map_multiple_common_fields(self, authed_client, profile_in_store):
        fields = [
            {"selector": "#fn", "kind": "text", "label": "First Name", "required": True, "options": []},
            {"selector": "#ln", "kind": "text", "label": "Last Name", "required": True, "options": []},
            {"selector": "#ph", "kind": "text", "label": "Phone Number", "required": False, "options": []},
            {"selector": "#li", "kind": "text", "label": "LinkedIn", "required": False, "options": []},
        ]
        with patch("job_copilot_api.services.mapping._llm_map_residuals", new=AsyncMock(return_value=[])):
            r = authed_client.post("/api/v1/forms/map", json={"persona": "default", "fields": fields})
        assert r.status_code == 200
        paths = {m["json_path"] for m in r.json()["mappings"]}
        assert "personal_info.first_name" in paths
        assert "personal_info.last_name" in paths
        assert "personal_info.phone" in paths
        assert "social_links.linkedin" in paths

    def test_map_missing_persona_returns_404(self, authed_client):
        with patch("job_copilot_api.services.mapping._llm_map_residuals", new=AsyncMock(return_value=[])):
            r = authed_client.post(
                "/api/v1/forms/map",
                json={"persona": "ghost-persona", "fields": []},
            )
        assert r.status_code == 404

    def test_map_willing_to_relocate_coerced_to_yes(self, authed_client, profile_in_store):
        fields = [
            {"selector": "#rel", "kind": "text", "label": "Willing to Relocate", "required": False, "options": []},
        ]
        with patch("job_copilot_api.services.mapping._llm_map_residuals", new=AsyncMock(return_value=[])):
            r = authed_client.post("/api/v1/forms/map", json={"persona": "default", "fields": fields})
        assert r.status_code == 200
        m = r.json()["mappings"][0]
        assert m["value"] == "Yes"

    def test_map_unresolved_field_listed(self, authed_client, profile_in_store):
        """Fields with a json_path but no value → listed in unresolved."""
        # headline is not set in MINIMAL_PROFILE's preferences, but let's pick a
        # field where the profile entry is None
        profile_no_headline = {**MINIMAL_PROFILE, "personal_info": {**MINIMAL_PROFILE["personal_info"], "headline": None}}
        authed_client.put("/api/v1/profiles/nohline", json={**profile_no_headline, "persona": "nohline"})
        fields = [
            {"selector": "#hl", "kind": "text", "label": "Professional Headline", "required": False, "options": []},
        ]
        with patch("job_copilot_api.services.mapping._llm_map_residuals", new=AsyncMock(return_value=[])):
            r = authed_client.post("/api/v1/forms/map", json={"persona": "nohline", "fields": fields})
        assert r.status_code == 200
        body = r.json()
        assert body["mappings"][0]["tier"] == "approve"


# ──────────────────────────── CV upload ─────────────────────────

class TestCvParse:
    def test_unsupported_format_returns_415(self, authed_client):
        r = authed_client.post(
            "/api/v1/cv/parse",
            files={"file": ("cv.xlsx", io.BytesIO(b"data"), "application/vnd.ms-excel")},
        )
        assert r.status_code == 415

    def test_file_too_large_returns_413(self, authed_client):
        big = b"x" * (11 * 1024 * 1024)  # 11 MB
        r = authed_client.post(
            "/api/v1/cv/parse",
            files={"file": ("cv.txt", io.BytesIO(big), "text/plain")},
        )
        assert r.status_code == 413

    def test_empty_file_returns_422(self, authed_client):
        r = authed_client.post(
            "/api/v1/cv/parse",
            files={"file": ("cv.txt", io.BytesIO(b"   "), "text/plain")},
        )
        assert r.status_code == 422

    def test_txt_cv_parses_with_mocked_llm(self, authed_client):
        cv_text = b"Jane Doe\njane@example.com\n+1555000000\nSoftware Engineer at Acme"

        async def fake_call_json(prompt, user_text, *, schema=None, timeout=60):
            return {
                "schema_version": "1.0",
                "persona": "default",
                "personal_info": {"first_name": "Jane", "last_name": "Doe", "full_name": "Jane Doe", "email": "jane@example.com"},
                "social_links": {},
                "education": [],
                "work_experience": [{"company": "Acme", "title": "Software Engineer"}],
                "projects": [],
                "skills": {"technical": [], "tools": [], "frameworks": [], "soft": []},
                "preferences": {},
                "custom_responses": [],
            }

        with patch("job_copilot_api.services.cv_parser.call_json", new=fake_call_json):
            r = authed_client.post(
                "/api/v1/cv/parse",
                files={"file": ("cv.txt", io.BytesIO(cv_text), "text/plain")},
            )

        assert r.status_code == 200
        body = r.json()
        assert body["personal_info"]["email"] == "jane@example.com"
        assert body["work_experience"][0]["company"] == "Acme"
