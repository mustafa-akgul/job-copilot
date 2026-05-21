"""Test fixtures.

JOB_COPILOT_DATABASE_URL must be set BEFORE any app module is imported,
because db.py creates the engine at module level from settings.database_url.
"""

import os

# Override DB to in-memory so tests never touch the real SQLite file.
os.environ["JOB_COPILOT_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
# Ensure cloud LLM provider so Literal validation passes (Ollama removed).
os.environ.setdefault("JOB_COPILOT_LLM_PROVIDER", "openai")
# No SUPABASE_JWT_SECRET in tests — deps.py falls back to dev_token comparison.
os.environ.setdefault("JOB_COPILOT_DEV_TOKEN", "dev-token")

import pytest
from fastapi.testclient import TestClient

from job_copilot_api.main import app

AUTH = {"Authorization": "Bearer dev-token"}

# Minimal valid CVProfile payload (all optional fields omitted).
MINIMAL_PROFILE = {
    "schema_version": "1.0",
    "persona": "default",
    "personal_info": {
        "first_name": "Jane",
        "last_name": "Doe",
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1-555-000-0000",
        "headline": "Software Engineer",
        "summary": "Experienced engineer.",
    },
    "social_links": {
        "linkedin": "https://linkedin.com/in/janedoe",
        "github": "https://github.com/janedoe",
    },
    "education": [
        {"institution": "MIT", "degree": "BSc", "field_of_study": "Computer Science"}
    ],
    "work_experience": [
        {"company": "Acme Corp", "title": "Senior Engineer", "is_current": True}
    ],
    "projects": [],
    "skills": {
        "technical": ["Python", "TypeScript"],
        "tools": ["Docker"],
        "frameworks": ["FastAPI", "React"],
        "soft": ["Communication"],
    },
    "preferences": {
        "expected_salary": "120000",
        "willing_to_relocate": True,
        "preferred_work_mode": "remote",
        "requires_visa_sponsorship": False,
    },
    "custom_responses": [],
}


@pytest.fixture(scope="session")
def client():
    """TestClient with lifespan (triggers init_db → creates in-memory tables)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def authed_client(client):
    """Convenience: client with dev-token header baked in."""

    class AuthedClient:
        def get(self, url, **kw):
            kw.setdefault("headers", {}).update(AUTH)
            return client.get(url, **kw)

        def post(self, url, **kw):
            kw.setdefault("headers", {}).update(AUTH)
            return client.post(url, **kw)

        def put(self, url, **kw):
            kw.setdefault("headers", {}).update(AUTH)
            return client.put(url, **kw)

        def delete(self, url, **kw):
            kw.setdefault("headers", {}).update(AUTH)
            return client.delete(url, **kw)

    return AuthedClient()


@pytest.fixture(scope="session")
def profile_in_store(authed_client):
    """Seed a profile so mapping tests can query against real data."""
    r = authed_client.put("/api/v1/profiles/default", json=MINIMAL_PROFILE)
    assert r.status_code == 200, r.text
    return r.json()
