from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.cases import get_case_service
from app.dependencies.auth import get_current_user
from app.main import app
from app.services.case_service import CaseService
from app.services.report_pdf_builder import build_excerpt_report_pdf
from app.services.report_service import ReportGenerationService

CASE_ID = "22222222-2222-2222-2222-222222222222"
USER_ID = "33333333-3333-3333-3333-333333333333"


class StubCaseRepo:
    def __init__(self):
        self.created = None

    def create_case(self, payload):
        self.created = payload
        return {"id": CASE_ID, **payload}

    def get_by_id(self, case_id):
        return {
            "id": CASE_ID, "created_by": USER_ID, "property_name": "Plot 42",
            "survey_number": None, "location": None, "status": "open",
        }


def teardown_function():
    app.dependency_overrides.clear()


def _login():
    app.dependency_overrides[get_current_user] = lambda: {"id": USER_ID, "role": "Reviewer"}


def test_service_stores_null_when_survey_number_missing():
    repo = StubCaseRepo()
    CaseService(repo).create(creator_id=USER_ID, property_name="Plot 42")
    assert repo.created["survey_number"] is None


@pytest.mark.parametrize("blank", ["", "   "])
def test_service_stores_null_instead_of_blank_string(blank):
    repo = StubCaseRepo()
    CaseService(repo).create(creator_id=USER_ID, property_name="Plot 42", survey_number=blank)
    assert repo.created["survey_number"] is None


def test_create_case_endpoint_without_survey_number_returns_null():
    _login()
    repo = StubCaseRepo()
    app.dependency_overrides[get_case_service] = lambda: CaseService(repo)

    res = TestClient(app).post("/api/v1/cases", json={"property_name": "Plot 42"})

    assert res.status_code == 201, res.text
    assert res.json()["survey_number"] is None
    assert repo.created["survey_number"] is None


def test_get_case_with_null_survey_number_serialises_null():
    _login()
    app.dependency_overrides[get_case_service] = lambda: CaseService(StubCaseRepo())

    res = TestClient(app).get(f"/api/v1/cases/{CASE_ID}")

    assert res.status_code == 200, res.text
    assert res.json()["survey_number"] is None


@pytest.mark.parametrize("survey", [None, ""])
def test_excerpt_pdf_builder_handles_missing_survey_number(survey):
    case = {"id": "case-1", "property_name": "Plot 42", "location": "Pune", "survey_number": survey}
    assert build_excerpt_report_pdf(case, []).startswith(b"%PDF")


@pytest.mark.parametrize("survey", [None, ""])
def test_verification_pdf_builder_handles_missing_survey_number(survey):
    uploads = []
    storage = SimpleNamespace(from_=lambda bucket: SimpleNamespace(upload=lambda **kw: uploads.append(kw)))
    report_repo = SimpleNamespace(client=SimpleNamespace(storage=storage), create_report=lambda p: p)
    case_repo = SimpleNamespace(get_by_id=lambda cid: {
        "id": CASE_ID, "property_name": "Plot 42", "location": None,
        "survey_number": survey, "status": "open",
    })

    ReportGenerationService(case_repo, report_repo).generate_pdf_report(CASE_ID, USER_ID)

    assert uploads and uploads[0]["file"].startswith(b"%PDF")
