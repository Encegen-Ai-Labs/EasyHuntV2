from fastapi.testclient import TestClient

from app.main import app
from app.dependencies.db import get_supabase_client

client = TestClient(app)


class FakeUserRepository:
    def __init__(self, db):
        self.db = db
        self.users = {}

    def get_by_email(self, email):
        return self.users.get(email)

    def create_user(self, user_data):
        self.users[user_data["email"]] = user_data
        return {
            "id": user_data["id"],
            "email": user_data["email"],
            "role": user_data["role"],
            "password_hash": user_data["password_hash"],
        }


def test_register_user_returns_token(monkeypatch):
    monkeypatch.setattr("app.api.v1.auth.UserRepository", FakeUserRepository)
    monkeypatch.setattr("app.api.v1.auth.get_password_hash", lambda password: "hashed-password")
    monkeypatch.setattr("app.api.v1.auth.create_access_token", lambda data: "test-token")

    app.dependency_overrides[get_supabase_client] = lambda: object()

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "password123", "role": "Vendor"},
    )

    assert response.status_code == 201
    assert response.json()["user_id"]
    assert response.json()["token"] == "test-token"

    app.dependency_overrides.clear()


def test_reviewer_registration_is_rejected(monkeypatch):
    monkeypatch.setattr("app.api.v1.auth.UserRepository", FakeUserRepository)

    app.dependency_overrides[get_supabase_client] = lambda: object()

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "reviewer@example.com", "password": "password123", "role": "Reviewer"},
    )

    assert response.status_code == 403
    app.dependency_overrides.clear()


def test_admin_login_uses_environment_credentials(monkeypatch):
    monkeypatch.setattr("app.api.v1.auth.UserRepository", FakeUserRepository)
    monkeypatch.setattr("app.api.v1.auth.verify_password", lambda plain, hashed: True)
    monkeypatch.setattr("app.api.v1.auth.create_access_token", lambda data: "login-token")
    monkeypatch.setattr("app.api.v1.auth.settings", type("Settings", (), {"ADMIN_EMAIL": "admin@example.com", "ADMIN_PASSWORD": "admin-pass"})())

    app.dependency_overrides[get_supabase_client] = lambda: object()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin-pass"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "login-token"
    assert response.json()["role"] == "Admin"

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
    monkeypatch.setattr(
        "app.api.v1.admin.get_current_user",
        lambda: {"id": "admin-id", "role": "Admin"},
    )
    app.dependency_overrides[get_supabase_client] = lambda: object()

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
