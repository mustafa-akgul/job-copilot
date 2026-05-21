"""Tests for personas management endpoints."""

from __future__ import annotations

from .conftest import AUTH, MINIMAL_PROFILE

# Dedicated personas so other tests can't clobber state.
_BASE = "personas-base"
_CLONE_SRC = "personas-clone-src"


def _seed(authed_client, persona: str):
    profile = {**MINIMAL_PROFILE, "persona": persona}
    r = authed_client.put(f"/api/v1/profiles/{persona}", json=profile)
    assert r.status_code == 200
    return r.json()


class TestPersonas:
    def test_list_personas_returns_list(self, client):
        r = client.get("/api/v1/personas", headers=AUTH)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_personas_includes_seeded(self, authed_client):
        _seed(authed_client, _BASE)
        r = authed_client.get("/api/v1/personas")
        assert r.status_code == 200
        body = r.json()
        assert any(p["persona"] == _BASE for p in body)

    def test_persona_meta_fields(self, authed_client):
        _seed(authed_client, _BASE)
        r = authed_client.get("/api/v1/personas")
        assert r.status_code == 200
        p = next(x for x in r.json() if x["persona"] == _BASE)
        assert "skill_count" in p
        assert "job_count" in p
        assert "education_count" in p
        # MINIMAL_PROFILE has 1 job and 1 education entry.
        assert p["job_count"] == 1
        assert p["education_count"] == 1

    def test_clone_persona(self, authed_client):
        _seed(authed_client, _CLONE_SRC)
        target = "personas-clone-target"
        r = authed_client.post(
            f"/api/v1/personas/{_CLONE_SRC}/clone",
            json={"new_persona": target},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["persona"] == target
        assert body["personal_info"]["email"] == "jane@example.com"

    def test_clone_nonexistent_returns_404(self, authed_client):
        r = authed_client.post(
            "/api/v1/personas/ghost-does-not-exist/clone",
            json={"new_persona": "copy"},
        )
        assert r.status_code == 404

    def test_clone_conflict_returns_409(self, authed_client):
        _seed(authed_client, "personas-conflict-src")
        authed_client.post(
            "/api/v1/personas/personas-conflict-src/clone",
            json={"new_persona": "personas-conflict-dup"},
        )
        # Second clone with same target should conflict.
        r = authed_client.post(
            "/api/v1/personas/personas-conflict-src/clone",
            json={"new_persona": "personas-conflict-dup"},
        )
        assert r.status_code == 409

    def test_no_auth_returns_401(self, client):
        r = client.get("/api/v1/personas")
        assert r.status_code == 401
