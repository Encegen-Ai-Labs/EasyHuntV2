"""Regression guard for app/schemas/flags.py::FlagResponse: source and
document_id must survive serialization. Phase 1 (pipeline_service.py) writes
both columns on every risk_flags row; before this schema included them,
FastAPI's response_model=FlagResponse silently stripped them from every
GET /flags response — see docs/DECISIONS.md D3 and the Phase 2 note in
docs/ROADMAP.md."""

from app.schemas.flags import FlagResponse


def test_flag_response_includes_source_and_document_id():
    flag = FlagResponse(
        id="11111111-1111-1111-1111-111111111111",
        case_id="22222222-2222-2222-2222-222222222222",
        document_id="33333333-3333-3333-3333-333333333333",
        flag_type="Litigation",
        severity="high",
        description="Document references an ongoing suit.",
        status="raised",
        source="llm",
    )

    dumped = flag.model_dump()
    assert dumped["source"] == "llm"
    assert str(dumped["document_id"]) == "33333333-3333-3333-3333-333333333333"


def test_flag_response_defaults_source_to_structural_when_omitted():
    # Matches the DB column's own default ('structural') for any row
    # inserted before migration 0006 added the source column.
    flag = FlagResponse(
        id="11111111-1111-1111-1111-111111111111",
        case_id="22222222-2222-2222-2222-222222222222",
        flag_type="Ownership Chain Gap",
        severity="high",
        description="A gap in the chain.",
        status="raised",
    )

    assert flag.source == "structural"
    assert flag.document_id is None
