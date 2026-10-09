import importlib

from fastapi.testclient import TestClient

from app.core.config import Settings


def _client(monkeypatch, origins):
    monkeypatch.setenv("CORS_ORIGINS", origins)
    import app.core.config as config
    monkeypatch.setattr(config, "settings", Settings())
    import app.main as main
    main = importlib.reload(main)
    return TestClient(main.app)


def _preflight(client, origin):
    return client.options(
        "/health",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )


def test_default_origin_is_localhost_3000(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert Settings(_env_file=None).cors_origin_list == ["http://localhost:3000"]


def test_listed_origins_allowed_with_credentials(monkeypatch):
    client = _client(monkeypatch, "https://app.example.com, http://localhost:3000/")
    for origin in ("https://app.example.com", "http://localhost:3000"):
        response = _preflight(client, origin)
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"


def test_unlisted_origin_is_not_allowed(monkeypatch):
    client = _client(monkeypatch, "https://app.example.com")
    response = _preflight(client, "https://evil.example.com")
    assert "access-control-allow-origin" not in response.headers
    assert response.status_code == 400
