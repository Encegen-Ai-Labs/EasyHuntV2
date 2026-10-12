import pytest

from app.core.security import get_password_hash, verify_password
from scripts.create_admin import create_admin


class FakeRepo:
    def __init__(self, existing=None):
        self.users = {u["email"]: u for u in (existing or [])}
        self.created = []

    def get_by_email(self, email):
        return self.users.get(email)

    def create_user(self, data):
        row = {**data, "id": "new-id"}
        self.users[row["email"]] = row
        self.created.append(row)
        return row


def test_creates_admin_with_login_compatible_hash():
    repo = FakeRepo()
    user = create_admin(repo, " boss@example.com ", "s3cret-pass", get_password_hash)

    row = repo.created[0]
    assert user["id"] == "new-id"
    assert row["email"] == "boss@example.com"
    assert row["role"] == "Admin"
    assert row["password"] != "s3cret-pass"
    # Same verify function the login endpoint uses.
    assert verify_password("s3cret-pass", row["password"])


def test_refuses_existing_email():
    repo = FakeRepo([{"email": "boss@example.com", "id": "x"}])
    with pytest.raises(ValueError, match="already exists"):
        create_admin(repo, "boss@example.com", "s3cret-pass", get_password_hash)
    assert repo.created == []


@pytest.mark.parametrize("email,password", [("", "s3cret-pass"), ("a@b.com", "short")])
def test_rejects_missing_email_or_weak_password(email, password):
    repo = FakeRepo()
    with pytest.raises(ValueError):
        create_admin(repo, email, password, get_password_hash)
    assert repo.created == []


def test_main_never_prints_password(monkeypatch, capsys):
    import scripts.create_admin as mod

    repo = FakeRepo()
    monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret-pass")
    monkeypatch.setattr("app.repositories.user_repo.UserRepository", lambda client: repo)
    monkeypatch.setattr("app.dependencies.db.get_supabase_service_client", lambda: object())

    assert mod.main() == 0
    out = capsys.readouterr()
    assert "s3cret-pass" not in out.out + out.err
    assert repo.created[0]["role"] == "Admin"

    assert mod.main() == 1  # second run: already exists
    out = capsys.readouterr()
    assert "s3cret-pass" not in out.out + out.err
