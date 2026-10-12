import pytest
from fastapi.testclient import TestClient

from app.api.v1 import review as review_module
from app.dependencies.auth import get_current_user
from app.dependencies.db import get_supabase_service_client
from app.main import app


class _Docs:
    def __init__(self, client):
        pass

    def get_by_id(self, document_id):
        return {"id": document_id, "case_id": "case-1"} if document_id == "doc-1" else None


class _Cases:
    def __init__(self, client):
        pass

    def get_by_id(self, case_id):
        return {"id": case_id, "created_by": "owner", "reviewer_id": None}


class _Service:
    def reopen_document_review(self, document_id):
        return {"reopened": document_id}

    def get_case_documents_for_review(self, case_id):
        return []


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(review_module, "DocumentRepository", _Docs)
    monkeypatch.setattr(review_module, "CaseRepository", _Cases)
    app.dependency_overrides[get_supabase_service_client] = lambda: object()
    app.dependency_overrides[review_module.get_review_service] = lambda: _Service()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _as(user_id, role):
    app.dependency_overrides[get_current_user] = lambda: {"id": user_id, "role": role}


def test_the_case_owner_can_reopen_a_document(client):
    _as("owner", "Reviewer")
    assert client.post("/api/v1/review/documents/doc-1/reopen").json() == {"reopened": "doc-1"}


def test_another_lawyer_cannot_reopen_or_list_it(client):
    _as("someone-else", "Reviewer")
    assert client.post("/api/v1/review/documents/doc-1/reopen").status_code == 403
    assert client.get("/api/v1/review/case-1/documents").status_code == 403


def test_an_admin_can_act_on_any_case(client):
    _as("admin", "Admin")
    assert client.post("/api/v1/review/documents/doc-1/reopen").status_code == 200


def test_an_unknown_document_is_a_404(client):
    _as("owner", "Reviewer")
    assert client.post("/api/v1/review/documents/nope/reopen").status_code == 404
