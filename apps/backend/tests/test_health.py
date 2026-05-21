"""Health + auth guard smoke tests."""

from .conftest import AUTH


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_map_requires_auth(client):
    r = client.post("/api/v1/forms/map", json={"persona": "default", "fields": []})
    assert r.status_code == 401


def test_map_wrong_token(client):
    r = client.post(
        "/api/v1/forms/map",
        json={"persona": "default", "fields": []},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert r.status_code == 401


def test_map_with_dev_token_but_no_profile(client):
    r = client.post(
        "/api/v1/forms/map",
        json={"persona": "nonexistent-persona", "fields": []},
        headers=AUTH,
    )
    assert r.status_code == 404


def test_profiles_requires_auth(client):
    assert client.get("/api/v1/profiles/default").status_code == 401


def test_cv_parse_requires_auth(client):
    import io
    r = client.post("/api/v1/cv/parse", files={"file": ("cv.txt", io.BytesIO(b"hello"), "text/plain")})
    assert r.status_code == 401
