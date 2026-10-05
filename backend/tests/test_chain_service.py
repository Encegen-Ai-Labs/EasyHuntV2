import pytest
from app.services.chain_service import ChainReconstructionService
from app.services.risk_service import RiskFlaggingService


CASE_ID = "test-case-00000000-0000-0000-0000-000000000001"


def make_record(order, owner, date, tx_type=None, survey="SY-123/A"):
    return {
        "case_id": CASE_ID,
        "sequence_order": order,
        "owner_name": owner,
        "transaction_date": date,
        "transaction_type": tx_type,
        "survey_number": survey,
    }


class FakeGenericRepo:
    def __init__(self, records):
        self._records = records

    def select(self, table, query_filters=None):
        if table == "ownership_chain" and query_filters:
            case_id = query_filters.get("case_id")
            return [r for r in self._records if r.get("case_id") == case_id]
        return self._records


class FakeFlagRepo:
    def __init__(self):
        self.flags = []

    def create_flag(self, payload):
        self.flags.append(payload)
        return payload


# ─── ChainReconstructionService ──────────────────────────────────────────────

class TestChainReconstruction:

    def _svc(self, records):
        return ChainReconstructionService(FakeGenericRepo(records))

    def test_empty_case_returns_no_data(self):
        result = self._svc([]).reconstruct_case_chain(CASE_ID)
        assert result["status"] == "no_data"
        assert result["chain"] == []
        assert result["gaps"] == []
        assert result["conflicts"] == []

    def test_clean_chain_three_docs(self):
        records = [
            make_record(1, "Ramesh Patil",  "1990-03-15", "Sale Deed"),
            make_record(2, "Suresh Kumar",  "2001-07-22", "Gift Deed"),
            make_record(3, "Anita Desai",   "2015-11-10", "Sale Deed"),
        ]
        result = self._svc(records).reconstruct_case_chain(CASE_ID)
        assert result["status"] == "reconstructed"
        assert len(result["chain"]) == 3
        assert result["gaps"] == []
        assert result["conflicts"] == []

    def test_chain_sorted_chronologically(self):
        # Records supplied out of order — service must sort them
        records = [
            make_record(3, "Anita Desai",  "2015-11-10", "Sale Deed"),
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed"),
            make_record(2, "Suresh Kumar", "2001-07-22", "Gift Deed"),
        ]
        result = self._svc(records).reconstruct_case_chain(CASE_ID)
        dates = [r["transaction_date"] for r in result["chain"]]
        assert dates == sorted(dates)

    def test_missing_date_records_sort_to_end(self):
        records = [
            make_record(2, "Suresh Kumar", None,         "Sale Deed"),  # no date
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed"),
        ]
        result = self._svc(records).reconstruct_case_chain(CASE_ID)
        assert result["chain"][0]["owner_name"] == "Ramesh Patil"
        assert result["chain"][1]["owner_name"] == "Suresh Kumar"

    def test_gap_detected_when_transaction_type_missing_on_new_owner(self):
        # Indian property docs: the transaction_type lives on the document that records
        # the *transfer to* the new owner (e.g. the Sale Deed is filed by/for the buyer).
        # If Suresh appears with no transaction_type, there's no documented legal basis.
        records = [
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed"),
            make_record(2, "Suresh Kumar", "2001-07-22", None),          # gap
            make_record(3, "Anita Desai",  "2015-11-10", "Sale Deed"),
        ]
        result = self._svc(records).reconstruct_case_chain(CASE_ID)
        assert len(result["gaps"]) == 1
        gap = result["gaps"][0]
        assert "Ramesh Patil" in gap["detail"]
        assert "Suresh Kumar" in gap["detail"]

    def test_no_gap_when_new_owner_has_transaction_type(self):
        records = [
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed"),
            make_record(2, "Suresh Kumar", "2001-07-22", "Sale Deed"),   # documented transfer
        ]
        result = self._svc(records).reconstruct_case_chain(CASE_ID)
        assert result["gaps"] == []

    def test_no_gap_when_same_owner_repeats_without_transaction_type(self):
        # Same owner appearing in two docs (e.g. mutation + tax receipt) — not a gap
        records = [
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed"),
            make_record(2, "Ramesh Patil", "1995-06-01", None),
        ]
        result = self._svc(records).reconstruct_case_chain(CASE_ID)
        assert result["gaps"] == []

    def test_survey_conflict_across_two_documents(self):
        records = [
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed", survey="SY-123/A"),
            make_record(2, "Suresh Kumar", "2001-07-22", "Sale Deed", survey="SY-456/B"),
        ]
        result = self._svc(records).reconstruct_case_chain(CASE_ID)
        assert len(result["conflicts"]) == 1
        conflict = result["conflicts"][0]
        assert conflict["type"] == "multiple_survey_numbers"
        assert "SY-123/A" in conflict["detail"] or "SY-456/B" in conflict["detail"]

    def test_no_conflict_when_all_same_survey(self):
        records = [
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed", survey="SY-123/A"),
            make_record(2, "Suresh Kumar", "2001-07-22", "Sale Deed", survey="SY-123/A"),
        ]
        result = self._svc(records).reconstruct_case_chain(CASE_ID)
        assert result["conflicts"] == []

    def test_get_current_owner_returns_chronological_last(self):
        records = [
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed"),
            make_record(2, "Suresh Kumar", "2001-07-22", "Sale Deed"),
            make_record(3, "Anita Desai",  "2015-11-10", "Sale Deed"),
        ]
        current = self._svc(records).get_current_owner(CASE_ID)
        assert current["owner_name"] == "Anita Desai"
        assert current["as_of_date"] == "2015-11-10"

    def test_get_current_owner_empty_chain(self):
        current = self._svc([]).get_current_owner(CASE_ID)
        assert current["owner_name"] is None
        assert current["as_of_date"] is None


# ─── RiskFlaggingService ──────────────────────────────────────────────────────

class TestRiskFlagging:

    def _setup(self, records):
        chain_svc = ChainReconstructionService(FakeGenericRepo(records))
        flag_repo = FakeFlagRepo()
        risk_svc = RiskFlaggingService(flag_repo, chain_svc)
        return risk_svc, flag_repo

    def test_clean_chain_creates_no_flags(self):
        records = [
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed"),
            make_record(2, "Suresh Kumar", "2001-07-22", "Gift Deed"),
            make_record(3, "Anita Desai",  "2015-11-10", "Sale Deed"),
        ]
        risk_svc, flag_repo = self._setup(records)
        flags = risk_svc.run_case_level_checks(CASE_ID)
        assert len(flags) == 0

    def test_gap_raises_high_severity_flag(self):
        records = [
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed"),
            make_record(2, "Suresh Kumar", "2001-07-22", None),
        ]
        risk_svc, flag_repo = self._setup(records)
        flags = risk_svc.run_case_level_checks(CASE_ID)
        flag_types = [f["flag_type"] for f in flags]
        assert "Ownership Chain Gap" in flag_types
        gap_flag = next(f for f in flags if f["flag_type"] == "Ownership Chain Gap")
        assert gap_flag["severity"] == "high"
        assert gap_flag["case_id"] == CASE_ID

    def test_survey_conflict_raises_high_severity_flag(self):
        records = [
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed", survey="SY-123/A"),
            make_record(2, "Suresh Kumar", "2001-07-22", "Sale Deed", survey="SY-456/B"),
        ]
        risk_svc, flag_repo = self._setup(records)
        flags = risk_svc.run_case_level_checks(CASE_ID)
        flag_types = [f["flag_type"] for f in flags]
        assert "Survey Number Conflict" in flag_types

    def test_single_record_raises_insufficient_history_flag(self):
        records = [make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed")]
        risk_svc, _ = self._setup(records)
        flags = risk_svc.run_case_level_checks(CASE_ID)
        flag_types = [f["flag_type"] for f in flags]
        assert "Insufficient Ownership History" in flag_types

    def test_empty_chain_raises_insufficient_history_flag(self):
        risk_svc, _ = self._setup([])
        flags = risk_svc.run_case_level_checks(CASE_ID)
        flag_types = [f["flag_type"] for f in flags]
        assert "Insufficient Ownership History" in flag_types

    def test_two_records_does_not_raise_insufficient_history(self):
        records = [
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed"),
            make_record(2, "Suresh Kumar", "2001-07-22", "Sale Deed"),
        ]
        risk_svc, _ = self._setup(records)
        flags = risk_svc.run_case_level_checks(CASE_ID)
        flag_types = [f["flag_type"] for f in flags]
        assert "Insufficient Ownership History" not in flag_types

    def test_gap_and_conflict_together_raise_two_flags(self):
        records = [
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed", survey="SY-123/A"),
            make_record(2, "Suresh Kumar", "2001-07-22", None,         survey="SY-456/B"),
        ]
        risk_svc, _ = self._setup(records)
        flags = risk_svc.run_case_level_checks(CASE_ID)
        flag_types = [f["flag_type"] for f in flags]
        assert "Ownership Chain Gap" in flag_types
        assert "Survey Number Conflict" in flag_types

    def test_flags_have_raised_status(self):
        records = [
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed", survey="SY-123/A"),
            make_record(2, "Suresh Kumar", "2001-07-22", None,         survey="SY-456/B"),
        ]
        risk_svc, _ = self._setup(records)
        flags = risk_svc.run_case_level_checks(CASE_ID)
        assert all(f["status"] == "raised" for f in flags)

    def test_one_flag_insert_failure_does_not_lose_others_or_crash(self, caplog):
        # Regression guard: before each create_flag call was individually
        # wrapped, one failing insert (e.g. finalize_case() called before
        # migration 0006 added risk_flags.source) would raise straight out
        # of run_case_level_checks() uncaught, both losing the other flags
        # this run would have created and crashing finalize_case() itself.
        class FlakyFlagRepo:
            def __init__(self):
                self.flags = []

            def create_flag(self, payload):
                if payload["flag_type"] == "Survey Number Conflict":
                    raise Exception("could not find the 'source' column of 'risk_flags'")
                self.flags.append(payload)
                return payload

        records = [
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed", survey="SY-123/A"),
            make_record(2, "Suresh Kumar", "2001-07-22", None,         survey="SY-456/B"),
        ]
        chain_svc = ChainReconstructionService(FakeGenericRepo(records))
        flag_repo = FlakyFlagRepo()
        risk_svc = RiskFlaggingService(flag_repo, chain_svc)

        with caplog.at_level("ERROR"):
            flags = risk_svc.run_case_level_checks(CASE_ID)

        flag_types = [f["flag_type"] for f in flags]
        assert "Survey Number Conflict" not in flag_types
        assert "Ownership Chain Gap" in flag_types
        assert any("risk_service.flag_create_failed" in r.message for r in caplog.records)

    def test_flags_are_tagged_structural_source(self):
        # Distinguishes these chain-derived flags from the LLM-derived ones
        # persisted in pipeline_service.py (see docs/DECISIONS.md D3) — both
        # land in the same risk_flags table/API, tagged by provenance.
        records = [
            make_record(1, "Ramesh Patil", "1990-03-15", "Sale Deed", survey="SY-123/A"),
            make_record(2, "Suresh Kumar", "2001-07-22", None,         survey="SY-456/B"),
        ]
        risk_svc, _ = self._setup(records)
        flags = risk_svc.run_case_level_checks(CASE_ID)
        assert len(flags) > 0
        assert all(f["source"] == "structural" for f in flags)
