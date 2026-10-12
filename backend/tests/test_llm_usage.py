from types import SimpleNamespace

import pytest

from app.core import context
from app.core.config import settings
from app.core.exceptions import PropertySystemException
from app.services import llm_usage as usage


class _Recorder:
    """A fake Supabase client that keeps what was inserted."""

    def __init__(self, rows_for_select=None, fail_insert=False):
        self.inserted = []
        self.rows = rows_for_select or []
        self.fail_insert = fail_insert

    def table(self, name):
        recorder = self

        class Table:
            def insert(self, row):
                if recorder.fail_insert:
                    raise RuntimeError('relation "llm_usage" does not exist')
                recorder.inserted.append((name, row))
                return self

            def select(self, *a, **k):
                return self

            def gte(self, *a, **k):
                return self

            def execute(self):
                return SimpleNamespace(data=recorder.rows)

        return Table()


@pytest.fixture
def recorder(monkeypatch):
    fake = _Recorder()
    monkeypatch.setattr(usage, "_client", lambda: fake)
    monkeypatch.setattr(usage, "_table_unavailable_until", 0.0)
    return fake


def _response(prompt=1000, candidates=200, thoughts=50):
    return SimpleNamespace(usage_metadata=SimpleNamespace(
        prompt_token_count=prompt, candidates_token_count=candidates, thoughts_token_count=thoughts))


def test_cost_uses_the_configured_prices(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PRICE_INPUT_PER_M", 1.0)
    monkeypatch.setattr(settings, "LLM_PRICE_OUTPUT_PER_M", 4.0)
    monkeypatch.setattr(settings, "TRANSLATE_PRICE_PER_M_CHARS", 20.0)

    assert usage.estimate_cost("page_transcription", 1_000_000, 500_000) == pytest.approx(3.0)
    assert usage.estimate_cost(usage.TRANSLATE_GOOGLE, 50_000, None) == pytest.approx(1.0)
    assert usage.estimate_cost("page_transcription", None, None) == 0


def test_thinking_tokens_count_as_output():
    assert usage.tokens_from_response(_response(1000, 200, 50)) == {"tokens_in": 1000, "tokens_out": 250}
    assert usage.tokens_from_response(SimpleNamespace()) == {"tokens_in": None, "tokens_out": None}


def test_a_call_writes_one_row_with_tokens_cost_latency_and_context(recorder):
    context.bind(case_id="case-1", document_id="doc-1", request_id="req-1")
    try:
        with usage.LlmCall("page_transcription", "gemini-x") as call:
            call.response = _response()
    finally:
        context.bind(case_id=None, document_id=None, request_id=None)

    (table, row), = recorder.inserted
    assert table == "llm_usage" and row["kind"] == "page_transcription" and row["status"] == "ok"
    assert row["tokens_in"] == 1000 and row["tokens_out"] == 250 and row["cost_usd"] > 0
    assert row["case_id"] == "case-1" and row["document_id"] == "doc-1" and row["request_id"] == "req-1"
    assert row["latency_ms"] >= 0 and row["error"] is None


def test_a_failed_call_is_recorded_scrubbed_and_still_raises(recorder, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key-secret-value-123")
    with pytest.raises(RuntimeError):
        with usage.LlmCall("field_extraction_text", "gemini-x"):
            raise RuntimeError("denied: gemini-key-secret-value-123")

    (_, row), = recorder.inserted
    assert row["status"] == "error" and "gemini-key-secret-value-123" not in row["error"]


def test_a_429_is_labelled_rate_limited(recorder):
    class TooMany(Exception):
        code = 429

    with pytest.raises(TooMany):
        with usage.LlmCall("page_transcription", "gemini-x"):
            raise TooMany("slow down")
    assert recorder.inserted[0][1]["status"] == "rate_limited"


def test_embeddings_without_a_token_count_are_estimated_from_characters(recorder):
    with usage.LlmCall(usage.EMBEDDING, "embed-x", chars_in=400) as call:
        call.response = SimpleNamespace()
    row = recorder.inserted[0][1]
    assert row["tokens_in"] == 100 and row["estimated"] is True


def test_recording_failure_never_breaks_the_call_and_is_not_retried_every_time(monkeypatch):
    broken = _Recorder(fail_insert=True)
    monkeypatch.setattr(usage, "_client", lambda: broken)
    monkeypatch.setattr(usage, "_table_unavailable_until", 0.0)

    with usage.LlmCall("page_transcription", "gemini-x") as call:
        call.response = _response()
    assert usage._table_unavailable_until > 0  # backs off instead of failing on every call

    healthy = _Recorder()
    monkeypatch.setattr(usage, "_client", lambda: healthy)
    with usage.LlmCall("page_transcription", "gemini-x") as call:
        call.response = _response()
    assert healthy.inserted == []  # still backing off


def test_generate_tracked_returns_the_response_and_records_it(recorder, monkeypatch):
    from app.services.llm_extractor import client_genai

    monkeypatch.setattr(client_genai.models, "generate_content", lambda **kw: _response())
    result = usage.generate_tracked("report_autofill", model="gemini-x", contents=["hi"])
    assert result.usage_metadata.prompt_token_count == 1000
    assert recorder.inserted[0][1]["kind"] == "report_autofill"


# ---- budget ----

def test_budget_blocks_new_work_once_the_limit_is_reached(monkeypatch):
    monkeypatch.setattr(settings, "DAILY_LLM_BUDGET_USD", 1.0)
    monkeypatch.setattr(usage, "_budget_cache", {"at": -1e9, "value": 0.0})
    monkeypatch.setattr(usage, "_client", lambda: _Recorder(rows_for_select=[{"cost_usd": "0.6"}, {"cost_usd": "0.5"}]))

    with pytest.raises(PropertySystemException) as error:
        usage.ensure_within_budget()
    assert error.value.status_code == 429 and "daily" in error.value.message.lower()


def test_budget_off_or_under_the_limit_lets_work_through(monkeypatch):
    monkeypatch.setattr(settings, "DAILY_LLM_BUDGET_USD", 0.0)
    usage.ensure_within_budget()

    monkeypatch.setattr(settings, "DAILY_LLM_BUDGET_USD", 5.0)
    monkeypatch.setattr(usage, "_budget_cache", {"at": -1e9, "value": 0.0})
    monkeypatch.setattr(usage, "_client", lambda: _Recorder(rows_for_select=[{"cost_usd": "0.2"}]))
    usage.ensure_within_budget()


def test_an_unreadable_budget_does_not_block_work(monkeypatch):
    monkeypatch.setattr(settings, "DAILY_LLM_BUDGET_USD", 1.0)
    monkeypatch.setattr(usage, "_budget_cache", {"at": -1e9, "value": 0.0})

    def broken():
        raise RuntimeError("db down")

    monkeypatch.setattr(usage, "_client", broken)
    usage.ensure_within_budget()


# ---- dashboard ----

def test_summary_groups_by_day_kind_and_case_and_lists_failures():
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).date().isoformat()
    rows = [
        {"created_at": f"{today}T10:00:00+00:00", "kind": "page_transcription", "tokens_in": 100, "tokens_out": 20, "cost_usd": 0.5, "status": "ok", "case_id": "c1"},
        {"created_at": f"{today}T11:00:00+00:00", "kind": "page_transcription", "tokens_in": 100, "tokens_out": 20, "cost_usd": 0.25, "status": "ok", "case_id": "c2"},
        {"created_at": f"{today}T12:00:00+00:00", "kind": "translation", "tokens_in": 10, "tokens_out": 5, "cost_usd": 0.0, "status": "error", "error": "boom", "case_id": "c1"},
        {"created_at": f"{today}T13:00:00+00:00", "kind": "embedding", "tokens_in": 10, "tokens_out": None, "cost_usd": 0.0, "status": "rate_limited"},
    ]

    summary = usage.summarize(rows, 7, {"c1": "Wagholi plot"})

    assert summary["total_cost_usd"] == 0.75 and summary["total_calls"] == 4
    assert summary["errors"] == 1 and summary["rate_limited"] == 1
    assert len(summary["by_day"]) == 7 and summary["by_day"][-1] == {"date": today, "cost_usd": 0.75, "calls": 4}
    assert summary["by_kind"][0]["kind"] == "page_transcription" and summary["by_kind"][0]["calls"] == 2
    assert summary["top_cases"][0] == {"case_id": "c1", "name": "Wagholi plot", "cost_usd": 0.5}
    assert {f["kind"] for f in summary["recent_failures"]} == {"translation", "embedding"}
    assert summary["estimated"] is True


def test_a_failed_call_is_not_costed(recorder):
    with pytest.raises(RuntimeError):
        with usage.LlmCall(usage.TRANSLATE_GOOGLE, "google-translate-v2", chars_in=5000):
            raise RuntimeError("401")
    assert recorder.inserted[0][1]["cost_usd"] == 0
