import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core import observability, rate_limiting
from app.core.config import Settings, settings
from app.core.observability import RequestContextMiddleware, scrub_event
from app.core.rate_limiting import limit_ip
from app.core.startup_checks import find_problems, run


@pytest.fixture
def limiting(monkeypatch):
    """Rate limiting on, with a fresh in-memory store."""
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_STORAGE_URL", "memory://")
    monkeypatch.setattr(rate_limiting, "_limiter", None)
    monkeypatch.setattr(rate_limiting, "_limiter_url", None)


def _app(**routes):
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/login", dependencies=[Depends(limit_ip("login", "RATE_LIMIT_LOGIN"))])
    def login():
        return {"ok": True}

    @app.get("/boom")
    def boom():
        raise RuntimeError("database password is hunter2hunter2")

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return app


# ---- rate limiting ----

def test_login_is_limited_per_address_with_a_retry_after(limiting, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "3/minute")
    client = TestClient(_app())

    statuses = [client.get("/login").status_code for _ in range(5)]
    blocked = client.get("/login")

    assert statuses == [200, 200, 200, 429, 429]
    assert blocked.headers["retry-after"] == "60" and "Too many requests" in blocked.json()["detail"]


def test_each_address_has_its_own_allowance(limiting, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "1/minute")
    monkeypatch.setattr(settings, "TRUST_PROXY", True)
    client = TestClient(_app())

    assert client.get("/login", headers={"x-forwarded-for": "10.0.0.1"}).status_code == 200
    assert client.get("/login", headers={"x-forwarded-for": "10.0.0.1"}).status_code == 429
    assert client.get("/login", headers={"x-forwarded-for": "10.0.0.2"}).status_code == 200


def test_forwarded_for_is_ignored_unless_the_proxy_is_trusted(limiting, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "1/minute")
    monkeypatch.setattr(settings, "TRUST_PROXY", False)
    client = TestClient(_app())

    assert client.get("/login", headers={"x-forwarded-for": "10.0.0.1"}).status_code == 200
    assert client.get("/login", headers={"x-forwarded-for": "10.0.0.2"}).status_code == 429  # spoofing does not help


def test_the_blanket_limit_stops_a_flood_but_not_health_checks(limiting, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT", "2/minute")
    app = _app()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    client = TestClient(app)
    assert [client.get("/ping").status_code for _ in range(3)] == [200, 200, 429]
    assert all(client.get("/health").status_code == 200 for _ in range(5))


def test_a_broken_limit_store_lets_requests_through(limiting, monkeypatch):
    class Broken:
        def hit(self, *args, **kwargs):
            raise ConnectionError("redis down")

    monkeypatch.setattr(rate_limiting, "_limiter", Broken())
    monkeypatch.setattr(rate_limiting, "_limiter_url", settings.RATE_LIMIT_STORAGE_URL)
    assert TestClient(_app()).get("/login").status_code == 200


def test_limiting_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "1/minute")
    client = TestClient(_app())
    assert all(client.get("/login").status_code == 200 for _ in range(4))


# ---- request id, headers, safe errors ----

def test_every_response_has_a_request_id_and_security_headers():
    response = TestClient(_app()).get("/ping")
    assert len(response.headers["x-request-id"]) >= 8
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


def test_a_sensible_incoming_request_id_is_kept_and_a_hostile_one_is_replaced():
    client = TestClient(_app())
    assert client.get("/ping", headers={"x-request-id": "trace-12345678"}).headers["x-request-id"] == "trace-12345678"
    replaced = client.get("/ping", headers={"x-request-id": "bad id\nwith newline"}).headers["x-request-id"]
    assert replaced != "bad id\nwith newline" and len(replaced) == 32


def test_an_unexpected_error_returns_a_generic_message_with_the_reference_and_no_details(caplog):
    client = TestClient(_app(), raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 500
    assert "hunter2hunter2" not in response.text and "RuntimeError" not in response.text
    assert response.headers["x-request-id"] in response.json()["detail"]


def test_hsts_is_sent_over_https_or_in_production(monkeypatch):
    client = TestClient(_app())
    assert "strict-transport-security" not in client.get("/ping").headers
    assert "strict-transport-security" in client.get("/ping", headers={"x-forwarded-proto": "https"}).headers


# ---- startup checks ----

def _cfg(**overrides):
    base = dict(
        _env_file=None, APP_ENV="production", APP_JWT_SECRET="x" * 40, SUPABASE_KEY="real-key",
        CORS_ORIGINS="https://app.example.com", ADMIN_PASSWORD="", RATE_LIMIT_ENABLED=True,
    )
    return Settings(**{**base, **overrides})


def test_a_safe_production_config_has_no_problems():
    assert find_problems(_cfg()) == []
    run(_cfg())  # does not raise


@pytest.mark.parametrize("overrides, fragment", [
    ({"APP_JWT_SECRET": "", "SUPABASE_JWT_SECRET": "dev-jwt-secret"}, "placeholder"),
    ({"APP_JWT_SECRET": "short"}, "shorter"),
    ({"APP_JWT_SECRET": ""}, "separate secret"),
    ({"CORS_ORIGINS": "*"}, "every origin"),
    ({"CORS_ORIGINS": "http://localhost:3000"}, "localhost"),
    ({"ADMIN_PASSWORD": "left-in-env"}, "ADMIN_PASSWORD"),
    ({"RATE_LIMIT_ENABLED": False}, "Rate limiting"),
])
def test_unsafe_settings_are_found(overrides, fragment):
    assert any(fragment in problem for problem in find_problems(_cfg(**overrides)))


def test_production_refuses_to_start_but_development_only_warns():
    with pytest.raises(RuntimeError, match="Refusing to start"):
        run(_cfg(CORS_ORIGINS="*"))
    run(_cfg(APP_ENV="development", CORS_ORIGINS="*"))  # warns, does not raise


# ---- sentry scrubbing ----

def test_sentry_events_lose_bodies_headers_cookies_and_user_details():
    event = {
        "request": {"url": "https://api/x", "data": {"q": "party name"}, "headers": {"authorization": "Bearer abc"},
                    "cookies": {"s": "1"}, "query_string": "q=secret", "method": "POST"},
        "user": {"email": "lawyer@firm.com"},
        "server_name": "host-1",
        "exception": {"values": []},
    }
    cleaned = scrub_event(event)
    assert cleaned["request"] == {"url": "https://api/x", "method": "POST"}
    assert "user" not in cleaned and "server_name" not in cleaned and "exception" in cleaned


def test_sentry_is_off_without_a_dsn(monkeypatch):
    monkeypatch.setattr(settings, "SENTRY_DSN", "")
    assert observability.init_sentry() is False


# ---- readiness ----

def test_readiness_reports_ok_when_the_database_answers(monkeypatch):
    from app import main

    class Query:
        def select(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def execute(self):
            return None

    class Db:
        def table(self, name):
            return Query()

    monkeypatch.setattr(main, "get_supabase_service_client", lambda: Db())
    monkeypatch.setattr(settings, "CELERY_ENABLED", False)
    response = TestClient(main.app).get("/health/ready")
    assert response.status_code == 200 and response.json()["checks"] == {"database": "ok"}


def test_readiness_is_503_and_says_what_is_down_without_leaking_why(monkeypatch):
    from app import main

    def broken():
        raise RuntimeError("could not connect to host db.internal password=hunter2hunter2")

    monkeypatch.setattr(main, "get_supabase_service_client", broken)
    monkeypatch.setattr(settings, "CELERY_ENABLED", False)
    response = TestClient(main.app).get("/health/ready")
    assert response.status_code == 503 and response.json()["checks"] == {"database": "down"}
    assert "hunter2" not in response.text and "db.internal" not in response.text
