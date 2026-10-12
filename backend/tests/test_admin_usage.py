from fastapi.testclient import TestClient

from app.dependencies.auth import get_current_user
from app.main import app
from app.services import llm_usage


def _as(role):
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "role": role}


def teardown_function():
    app.dependency_overrides.clear()


def test_admin_gets_the_usage_summary(monkeypatch):
    monkeypatch.setattr(llm_usage, "load_summary", lambda days: {"days": days, "total_cost_usd": 1.5})
    _as("Admin")
    response = TestClient(app).get("/api/v1/admin/usage?days=14")
    assert response.status_code == 200 and response.json() == {"days": 14, "total_cost_usd": 1.5}


def test_a_lawyer_cannot_see_usage(monkeypatch):
    monkeypatch.setattr(llm_usage, "load_summary", lambda days: {})
    _as("Reviewer")
    assert TestClient(app).get("/api/v1/admin/usage").status_code == 403


def test_a_missing_table_gives_a_clear_message_not_a_stack_trace(monkeypatch):
    def broken(days):
        raise RuntimeError('relation "llm_usage" does not exist')

    monkeypatch.setattr(llm_usage, "load_summary", broken)
    _as("Admin")
    response = TestClient(app).get("/api/v1/admin/usage")
    assert response.status_code == 503 and "0010_llm_usage.sql" in response.json()["detail"]
    assert "relation" not in response.text


def test_days_is_bounded():
    _as("Admin")
    assert TestClient(app).get("/api/v1/admin/usage?days=0").status_code == 422
    assert TestClient(app).get("/api/v1/admin/usage?days=400").status_code == 422
