from fastapi.testclient import TestClient

from app.api.v1.documents import get_doc_page_repo, get_doc_service
from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError
from app.dependencies.auth import get_current_user
from app.main import app

DOC_ID = "11111111-1111-1111-1111-111111111111"
CASE_ID = "22222222-2222-2222-2222-222222222222"


class StubDocRepo:
    def __init__(self, doc=None):
        self.doc = doc

    def get_by_id(self, doc_id):
        return self.doc if self.doc and self.doc["id"] == doc_id else None

    def list_by_case(self, case_id):
        return [
            {
                "id": DOC_ID,
                "case_id": case_id,
                "file_name": "deed.pdf",
                "file_path": f"cases/{case_id}/deed.pdf",
                "file_size": 1024,
                "mime_type": "application/pdf",
                "status": "llm_done",
                "created_at": "2026-08-01T00:00:00Z",
            }
        ]


class StubDocService:
    def __init__(self, doc_repo=None, forbidden=False):
        self.doc_repo = doc_repo or StubDocRepo()
        self.forbidden = forbidden

    def authorize_case_access(self, case_id, current_user):
        if self.forbidden:
            raise PermissionDeniedError("not your case")


def _login():
    app.dependency_overrides[get_current_user] = lambda: {"id": "reviewer-1", "role": "Reviewer"}


def teardown_function():
    app.dependency_overrides.clear()


def test_list_documents_returns_documents_for_case():
    _login()
    app.dependency_overrides[get_doc_service] = lambda: StubDocService()

    client = TestClient(app)
    response = client.get(
        "/api/v1/documents", params={"case_id": CASE_ID}, headers={"Authorization": "Bearer test"}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["file_name"] == "deed.pdf"


def test_list_documents_requires_case_id():
    _login()
    app.dependency_overrides[get_doc_service] = lambda: StubDocService()

    client = TestClient(app)
    response = client.get("/api/v1/documents", headers={"Authorization": "Bearer test"})

    assert response.status_code == 422


def test_list_documents_rejects_unowned_case():
    _login()
    app.dependency_overrides[get_doc_service] = lambda: StubDocService(forbidden=True)

    client = TestClient(app)
    response = client.get(
        "/api/v1/documents", params={"case_id": CASE_ID}, headers={"Authorization": "Bearer test"}
    )

    assert response.status_code == 403


def test_get_document_pages_returns_pages_sorted_by_page_number():
    _login()
    doc_repo = StubDocRepo(doc={"id": DOC_ID, "case_id": CASE_ID})
    app.dependency_overrides[get_doc_service] = lambda: StubDocService(doc_repo=doc_repo)

    class StubDocPageRepo:
        def list_by_document(self, document_id):
            assert document_id == DOC_ID
            return [
                {"page_number": 2, "original_text": "page two", "english_text": "page two"},
                {"page_number": 1, "original_text": "page one", "english_text": "page one"},
            ]

    app.dependency_overrides[get_doc_page_repo] = lambda: StubDocPageRepo()

    client = TestClient(app)
    response = client.get(f"/api/v1/documents/{DOC_ID}/pages", headers={"Authorization": "Bearer test"})

    assert response.status_code == 200
    body = response.json()
    assert [p["page_number"] for p in body["pages"]] == [1, 2]
    assert body["pages"][0]["original_text"] == "page one"


def test_get_document_pages_404s_for_missing_document():
    _login()
    app.dependency_overrides[get_doc_service] = lambda: StubDocService(doc_repo=StubDocRepo(doc=None))
    app.dependency_overrides[get_doc_page_repo] = lambda: object()

    client = TestClient(app)
    response = client.get(f"/api/v1/documents/{DOC_ID}/pages", headers={"Authorization": "Bearer test"})

    assert response.status_code == 404


def test_translate_document_persists_and_returns_translated_pages(monkeypatch):
    _login()
    doc_repo = StubDocRepo(doc={"id": DOC_ID, "case_id": CASE_ID})
    app.dependency_overrides[get_doc_service] = lambda: StubDocService(doc_repo=doc_repo)

    class StubDocPageRepo:
        def __init__(self):
            self.updated_with = None

        def list_by_document(self, document_id):
            assert document_id == DOC_ID
            return [{"page_number": 1, "original_text": "bonjour", "english_text": None}]

        def update_english_text_bulk(self, document_id, pages):
            self.updated_with = (document_id, pages)
            return pages

    stub_repo = StubDocPageRepo()
    app.dependency_overrides[get_doc_page_repo] = lambda: stub_repo

    monkeypatch.setattr(
        "app.api.v1.documents.translate_pages",
        lambda pages: [{**p, "english_text": "hello"} for p in pages],
    )

    client = TestClient(app)
    response = client.post(f"/api/v1/documents/{DOC_ID}/translate", headers={"Authorization": "Bearer test"})

    assert response.status_code == 200
    body = response.json()
    assert body["pages"][0]["english_text"] == "hello"
    assert stub_repo.updated_with[0] == DOC_ID
    assert stub_repo.updated_with[1] == [{"page_number": 1, "english_text": "hello"}]


def test_translate_document_rejects_document_with_no_pages_yet():
    _login()
    doc_repo = StubDocRepo(doc={"id": DOC_ID, "case_id": CASE_ID})
    app.dependency_overrides[get_doc_service] = lambda: StubDocService(doc_repo=doc_repo)

    class EmptyDocPageRepo:
        def list_by_document(self, document_id):
            return []

    app.dependency_overrides[get_doc_page_repo] = lambda: EmptyDocPageRepo()

    client = TestClient(app)
    response = client.post(f"/api/v1/documents/{DOC_ID}/translate", headers={"Authorization": "Bearer test"})

    assert response.status_code == 400


def test_translate_document_404s_for_missing_document():
    _login()
    app.dependency_overrides[get_doc_service] = lambda: StubDocService(doc_repo=StubDocRepo(doc=None))
    app.dependency_overrides[get_doc_page_repo] = lambda: object()

    client = TestClient(app)
    response = client.post(f"/api/v1/documents/{DOC_ID}/translate", headers={"Authorization": "Bearer test"})

    assert response.status_code == 404


# --- PATCH /{id}/pages/{page_number} ---

class StubDocPageRepoForUpdate:
    def __init__(self, existing_page=None):
        self.existing_page = existing_page or {"document_id": DOC_ID, "page_number": 1}
        self.last_update = None

    def update_page_text(self, document_id, page_number, data):
        self.last_update = (document_id, page_number, data)
        if document_id != self.existing_page["document_id"] or page_number != self.existing_page["page_number"]:
            return None
        return {**self.existing_page, **data}


def test_update_document_page_saves_original_text_and_regenerates_embedding(monkeypatch):
    _login()
    doc_repo = StubDocRepo(doc={"id": DOC_ID, "case_id": CASE_ID})
    app.dependency_overrides[get_doc_service] = lambda: StubDocService(doc_repo=doc_repo)

    stub_repo = StubDocPageRepoForUpdate()
    app.dependency_overrides[get_doc_page_repo] = lambda: stub_repo

    monkeypatch.setattr(
        "app.api.v1.documents.embed_text",
        lambda text: {"success": True, "embedding": [0.1, 0.2], "error": None},
    )

    client = TestClient(app)
    response = client.patch(
        f"/api/v1/documents/{DOC_ID}/pages/1",
        json={"original_text": "corrected दिनांक text"},
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 200
    assert response.json()["original_text"] == "corrected दिनांक text"
    _, _, data = stub_repo.last_update
    assert data["original_text"] == "corrected दिनांक text"
    assert data["embedding"] == [0.1, 0.2]


def test_update_document_page_keeps_old_embedding_when_reembed_fails(monkeypatch):
    _login()
    doc_repo = StubDocRepo(doc={"id": DOC_ID, "case_id": CASE_ID})
    app.dependency_overrides[get_doc_service] = lambda: StubDocService(doc_repo=doc_repo)

    stub_repo = StubDocPageRepoForUpdate()
    app.dependency_overrides[get_doc_page_repo] = lambda: stub_repo

    monkeypatch.setattr(
        "app.api.v1.documents.embed_text",
        lambda text: {"success": False, "embedding": None, "error": "Gemini timeout"},
    )

    client = TestClient(app)
    response = client.patch(
        f"/api/v1/documents/{DOC_ID}/pages/1",
        json={"original_text": "corrected text"},
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 200
    _, _, data = stub_repo.last_update
    assert "embedding" not in data  # old embedding left untouched, not nulled out
    assert data["original_text"] == "corrected text"


def test_update_document_page_updates_english_text_without_reembedding(monkeypatch):
    _login()
    doc_repo = StubDocRepo(doc={"id": DOC_ID, "case_id": CASE_ID})
    app.dependency_overrides[get_doc_service] = lambda: StubDocService(doc_repo=doc_repo)

    stub_repo = StubDocPageRepoForUpdate()
    app.dependency_overrides[get_doc_page_repo] = lambda: stub_repo

    embed_calls = []
    monkeypatch.setattr(
        "app.api.v1.documents.embed_text",
        lambda text: embed_calls.append(text) or {"success": True, "embedding": [1.0], "error": None},
    )

    client = TestClient(app)
    response = client.patch(
        f"/api/v1/documents/{DOC_ID}/pages/1",
        json={"english_text": "corrected english"},
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 200
    assert response.json()["english_text"] == "corrected english"
    assert embed_calls == []  # no re-embed call for an English-only edit
    _, _, data = stub_repo.last_update
    assert "original_text" not in data


def test_update_document_page_rejects_empty_payload():
    _login()
    doc_repo = StubDocRepo(doc={"id": DOC_ID, "case_id": CASE_ID})
    app.dependency_overrides[get_doc_service] = lambda: StubDocService(doc_repo=doc_repo)
    app.dependency_overrides[get_doc_page_repo] = lambda: StubDocPageRepoForUpdate()

    client = TestClient(app)
    response = client.patch(
        f"/api/v1/documents/{DOC_ID}/pages/1",
        json={},
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 400


def test_update_document_page_404s_for_missing_document():
    _login()
    app.dependency_overrides[get_doc_service] = lambda: StubDocService(doc_repo=StubDocRepo(doc=None))
    app.dependency_overrides[get_doc_page_repo] = lambda: StubDocPageRepoForUpdate()

    client = TestClient(app)
    response = client.patch(
        f"/api/v1/documents/{DOC_ID}/pages/1",
        json={"original_text": "x"},
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 404


def test_update_document_page_404s_for_missing_page(monkeypatch):
    _login()
    doc_repo = StubDocRepo(doc={"id": DOC_ID, "case_id": CASE_ID})
    app.dependency_overrides[get_doc_service] = lambda: StubDocService(doc_repo=doc_repo)
    app.dependency_overrides[get_doc_page_repo] = lambda: StubDocPageRepoForUpdate(
        existing_page={"document_id": DOC_ID, "page_number": 1}
    )
    monkeypatch.setattr(
        "app.api.v1.documents.embed_text",
        lambda text: {"success": True, "embedding": [0.1], "error": None},
    )

    client = TestClient(app)
    response = client.patch(
        f"/api/v1/documents/{DOC_ID}/pages/99",
        json={"original_text": "x"},
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 404


# --- GET /{id}/pages/{page_number}/enhanced-image ---

class StubDocServiceWithClient(StubDocService):
    """Adds the doc_repo.client.storage surface the enhanced-image route
    reads directly (it doesn't go through authorize_case_access at all —
    Admin-only, checked via RoleRequirement instead)."""

    def __init__(self, doc_repo=None, signed_url="https://example.com/enhanced.png", raise_on_sign=False):
        super().__init__(doc_repo=doc_repo)
        self._signed_url = signed_url
        self._raise_on_sign = raise_on_sign
        self.doc_repo.client = self._make_client()

    def _make_client(self):
        def create_signed_url(path, ttl):
            if self._raise_on_sign:
                raise RuntimeError("object not found")
            return {"signedURL": self._signed_url} if self._signed_url else {}

        bucket = type("Bucket", (), {"create_signed_url": staticmethod(create_signed_url)})()
        storage = type("Storage", (), {"from_": staticmethod(lambda bucket_name: bucket)})()
        return type("Client", (), {"storage": storage})()


def _login_admin():
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin-1", "role": "Admin"}


def test_get_enhanced_page_image_returns_signed_url():
    _login_admin()
    doc_repo = StubDocRepo(doc={"id": DOC_ID, "case_id": CASE_ID})
    app.dependency_overrides[get_doc_service] = lambda: StubDocServiceWithClient(doc_repo=doc_repo)

    client = TestClient(app)
    response = client.get(
        f"/api/v1/documents/{DOC_ID}/pages/1/enhanced-image", headers={"Authorization": "Bearer test"}
    )

    assert response.status_code == 200
    assert response.json()["url"] == "https://example.com/enhanced.png"


def test_get_enhanced_page_image_404s_when_not_yet_uploaded():
    _login_admin()
    doc_repo = StubDocRepo(doc={"id": DOC_ID, "case_id": CASE_ID})
    app.dependency_overrides[get_doc_service] = lambda: StubDocServiceWithClient(doc_repo=doc_repo, raise_on_sign=True)

    client = TestClient(app)
    response = client.get(
        f"/api/v1/documents/{DOC_ID}/pages/1/enhanced-image", headers={"Authorization": "Bearer test"}
    )

    assert response.status_code == 404


def test_get_enhanced_page_image_404s_for_missing_document():
    _login_admin()
    app.dependency_overrides[get_doc_service] = lambda: StubDocServiceWithClient(doc_repo=StubDocRepo(doc=None))

    client = TestClient(app)
    response = client.get(
        f"/api/v1/documents/{DOC_ID}/pages/1/enhanced-image", headers={"Authorization": "Bearer test"}
    )

    assert response.status_code == 404


def test_get_enhanced_page_image_rejects_non_admin():
    _login()  # Reviewer, not Admin
    doc_repo = StubDocRepo(doc={"id": DOC_ID, "case_id": CASE_ID})
    app.dependency_overrides[get_doc_service] = lambda: StubDocServiceWithClient(doc_repo=doc_repo)

    client = TestClient(app)
    response = client.get(
        f"/api/v1/documents/{DOC_ID}/pages/1/enhanced-image", headers={"Authorization": "Bearer test"}
    )

    assert response.status_code == 403


def test_update_document_page_rejects_unowned_case():
    _login()
    doc_repo = StubDocRepo(doc={"id": DOC_ID, "case_id": CASE_ID})
    app.dependency_overrides[get_doc_service] = lambda: StubDocService(doc_repo=doc_repo, forbidden=True)
    app.dependency_overrides[get_doc_page_repo] = lambda: StubDocPageRepoForUpdate()

    client = TestClient(app)
    response = client.patch(
        f"/api/v1/documents/{DOC_ID}/pages/1",
        json={"original_text": "x"},
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 403
