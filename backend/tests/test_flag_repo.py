"""Tests for app/repositories/flag_repo.py — specifically the two live-DB
bugs fixed here: create_flag targeting a nonexistent "flags" table (the
real table is "risk_flags"), and risk_flags.document_id/resolved_by both
carrying a stray DEFAULT that points at a row no longer present in
documents/users, which fires an FK violation on any insert that omits
those keys. Both were verified directly against the live Supabase project
before/after the fix; these tests lock the behavior in without needing
that live access."""

from app.repositories.flag_repo import FlagRepository, FLAGS_TABLE


class _FakeInsertClient:
    """Minimal fake Supabase client that only needs to support the
    table(...).insert(...).execute() chain create_flag uses, recording
    which table and payload it was called with."""
    def __init__(self):
        self.table_name = None
        self.inserted_payload = None

    def table(self, name):
        self.table_name = name
        return self

    def insert(self, data):
        self.inserted_payload = data
        return self

    def execute(self):
        return type("Response", (), {"data": [{"id": "flag-1", **self.inserted_payload}]})()


def test_flags_table_constant_is_risk_flags():
    # The live table is "risk_flags" — regression guard against
    # reintroducing the plain "flags" name that doesn't exist in the schema.
    assert FLAGS_TABLE == "risk_flags"


def test_create_flag_targets_risk_flags_table():
    client = _FakeInsertClient()
    repo = FlagRepository(client)

    repo.create_flag({"case_id": "case-1", "flag_type": "Test", "severity": "low", "status": "raised"})

    assert client.table_name == "risk_flags"


def test_create_flag_defaults_document_id_and_resolved_by_to_none():
    client = _FakeInsertClient()
    repo = FlagRepository(client)

    repo.create_flag({"case_id": "case-1", "flag_type": "Test", "severity": "low", "status": "raised"})

    assert client.inserted_payload["document_id"] is None
    assert client.inserted_payload["resolved_by"] is None


def test_create_flag_lets_caller_override_document_id():
    client = _FakeInsertClient()
    repo = FlagRepository(client)

    repo.create_flag({
        "case_id": "case-1",
        "flag_type": "Test",
        "severity": "low",
        "status": "raised",
        "document_id": "doc-42",
    })

    assert client.inserted_payload["document_id"] == "doc-42"
    assert client.inserted_payload["resolved_by"] is None
