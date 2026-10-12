from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencies.auth import get_current_user
from app.dependencies.db import get_supabase_service_client
from app.main import app

client = TestClient(app)


class FakeUserRepository:
    def __init__(self, db):
        self.db = db
        self.users = {}

    def get_by_email(self, email):
        return self.users.get(email)

    def create_user(self, user_data):
        user_data = {**user_data, "id": str(uuid4())}
        self.users[user_data["email"]] = user_data
        return user_data


def test_register_endpoint_no_longer_exists(monkeypatch):
    # Self-registration has been removed entirely — reviewer accounts are
    # created only by an admin via POST /admin/reviewers (see test_admin_can_create_reviewer).
    app.dependency_overrides[get_supabase_service_client] = lambda: object()

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "password123", "organisation_name": "Test Org"},
    )

    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_admin_login_uses_database_row_not_env_credentials(monkeypatch):
    class AdminRepo(FakeUserRepository):
        def get_by_email(self, email):
            return {"id": "admin-uuid", "email": email, "password": "hash", "role": "Admin"}

    monkeypatch.setattr("app.api.v1.auth.UserRepository", AdminRepo)
    monkeypatch.setattr("app.api.v1.auth.verify_password", lambda plain, hashed: plain == "admin-pass")
    monkeypatch.setattr("app.api.v1.auth.create_access_token", lambda data: f"{data['sub']}:{data['role']}")
    app.dependency_overrides[get_supabase_service_client] = lambda: object()

    ok = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-pass"})
    assert ok.status_code == 200
    assert ok.json()["access_token"] == "admin-uuid:Admin"
    assert ok.json()["user_id"] == "admin-uuid"
    assert ok.json()["role"] == "Admin"

    bad = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "wrong"})
    assert bad.status_code == 401

    app.dependency_overrides.clear()


def test_admin_can_create_reviewer(monkeypatch):
    class AdminRepository(FakeUserRepository):
        def get_by_email(self, email):
            return None

        def create_user(self, user_data):
            user_data["id"] = "reviewer-id"
            return user_data

    monkeypatch.setattr("app.api.v1.admin.UserRepository", AdminRepository)
    monkeypatch.setattr("app.api.v1.admin.get_password_hash", lambda password: "argon2-hash")
    app.dependency_overrides[get_supabase_service_client] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin-id", "role": "Admin"}

    response = client.post(
        "/api/v1/admin/reviewers",
        headers={"Authorization": "Bearer test-token"},
        json={
            "email": "reviewer@example.com",
            "password": "password123",
            "organisation_name": "Example Organisation",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "user_id": "reviewer-id",
        "email": "reviewer@example.com",
        "role": "Reviewer",
        "password": "password123",
    }

    app.dependency_overrides.clear()
