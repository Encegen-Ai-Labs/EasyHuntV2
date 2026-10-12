"""Records what every paid model call costs, and guards against runaway spend.

Every call to Gemini or Cloud Translation goes through LlmCall:

    with LlmCall("page_transcription", GEMINI_MODEL) as call:
        response = client.models.generate_content(...)
        call.response = response

On exit it writes one row to llm_usage (kind, model, tokens, estimated cost,
latency, status) and one structured log line. Recording is best-effort: a
failure to record never breaks, or noticeably slows, the call.

Costs are ESTIMATES from the prices in settings (LLM_PRICE_*): the provider does
not return a bill per call. Compare the total with the Google Cloud billing
page before relying on it.
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core import context
from app.core.config import settings
from app.core.exceptions import PropertySystemException
from app.core.logging import logger
from app.core.redaction import safe_error
from app.services.rate_limit import is_rate_limit_error

TABLE = "llm_usage"
TRANSLATE_GOOGLE = "translate_google"
EMBEDDING = "embedding"
BUDGET_CACHE_SECONDS = 30
TABLE_RETRY_SECONDS = 300

_budget_cache: Dict[str, float] = {"at": -1e9, "value": 0.0}
_table_unavailable_until = 0.0


def estimate_cost(kind: str, tokens_in: Optional[int], tokens_out: Optional[int]) -> float:
    """Estimated US dollars for one call (see the module note on prices)."""
    tokens_in, tokens_out = tokens_in or 0, tokens_out or 0
    if kind == TRANSLATE_GOOGLE:  # tokens_in holds characters here
        return tokens_in / 1_000_000 * settings.TRANSLATE_PRICE_PER_M_CHARS
    if kind == EMBEDDING:
        return tokens_in / 1_000_000 * settings.LLM_PRICE_EMBEDDING_PER_M
    return (
        tokens_in / 1_000_000 * settings.LLM_PRICE_INPUT_PER_M
        + tokens_out / 1_000_000 * settings.LLM_PRICE_OUTPUT_PER_M
    )


def tokens_from_response(response: Any) -> Dict[str, Optional[int]]:
    """Token counts from a google-genai response. Thinking tokens are billed as
    output, so they are counted with it."""
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return {"tokens_in": None, "tokens_out": None}
    prompt = getattr(usage, "prompt_token_count", None)
    out = (getattr(usage, "candidates_token_count", None) or 0) + (getattr(usage, "thoughts_token_count", None) or 0)
    return {"tokens_in": prompt, "tokens_out": out if (out or prompt is not None) else None}


def _client():
    from app.dependencies.db import get_supabase_service_client

    return get_supabase_service_client()


def record_usage(
    kind: str,
    model: str,
    *,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    started: Optional[float] = None,
    status: str = "ok",
    error: Optional[BaseException] = None,
    estimated: bool = False,
) -> None:
    """Writes the usage row and the log line. Never raises."""
    global _table_unavailable_until
    latency_ms = int((time.monotonic() - started) * 1000) if started is not None else None
    # A rejected or failed call is not billed.
    cost = estimate_cost(kind, tokens_in, tokens_out) if status == "ok" else 0.0
    ctx = context.current()
    error_text = safe_error(error) if error is not None else None

    logger.info(
        "llm.call | kind=%s model=%s status=%s tokens_in=%s tokens_out=%s cost_usd=%.6f latency_ms=%s",
        kind, model, status, tokens_in, tokens_out, cost, latency_ms,
    )
    if time.monotonic() < _table_unavailable_until:
        return
    row = {
        "kind": kind, "model": model, "tokens_in": tokens_in, "tokens_out": tokens_out,
        "cost_usd": round(cost, 6), "estimated": estimated, "latency_ms": latency_ms,
        "status": status, "error": error_text,
        "case_id": ctx.get("case_id"), "document_id": ctx.get("document_id"),
        "user_id": ctx.get("user_id"), "request_id": ctx.get("request_id"),
    }
    try:
        _client().table(TABLE).insert(row).execute()
    except Exception as exc:  # table missing, DB down, bad id: usage tracking must not break the call
        _table_unavailable_until = time.monotonic() + TABLE_RETRY_SECONDS
        logger.warning("llm.usage_not_recorded | reason=%s retry_in_seconds=%s", safe_error(exc, 160), TABLE_RETRY_SECONDS)


class LlmCall:
    """Context manager around one model call; see the module docstring."""

    def __init__(self, kind: str, model: str, *, chars_in: Optional[int] = None):
        self.kind, self.model, self.chars_in = kind, model, chars_in
        self.response: Any = None
        self._started = 0.0

    def __enter__(self) -> "LlmCall":
        self._started = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is not None:
            status = "rate_limited" if is_rate_limit_error(exc) else "error"
            record_usage(self.kind, self.model, tokens_in=self.chars_in, started=self._started, status=status, error=exc)
            return False
        tokens = tokens_from_response(self.response) if self.response is not None else {"tokens_in": None, "tokens_out": None}
        estimated = False
        if tokens["tokens_in"] is None and self.chars_in is not None:
            # No token count from the provider: use characters (translation) or chars/4 (embeddings).
            tokens["tokens_in"] = self.chars_in if self.kind == TRANSLATE_GOOGLE else max(1, self.chars_in // 4)
            estimated = self.kind != TRANSLATE_GOOGLE
        record_usage(self.kind, self.model, started=self._started, estimated=estimated, **tokens)
        return False


def generate_tracked(kind: str, **kwargs: Any) -> Any:
    """client.models.generate_content(**kwargs), recorded under `kind`."""
    from app.services.llm_extractor import client_genai

    with LlmCall(kind, kwargs.get("model", "unknown")) as call:
        response = client_genai.models.generate_content(**kwargs)
        call.response = response
    return response


def embed_tracked(**kwargs: Any) -> Any:
    """client.models.embed_content(**kwargs), recorded as an embedding call."""
    from app.services.llm_extractor import client_genai

    contents = kwargs.get("contents")
    chars = len(contents) if isinstance(contents, str) else None
    with LlmCall(EMBEDDING, kwargs.get("model", "unknown"), chars_in=chars) as call:
        response = client_genai.models.embed_content(**kwargs)
        call.response = response
    return response


# ---- budget guard ----------------------------------------------------------

def _start_of_today_utc() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def spent_today_usd() -> float:
    """Estimated spend since midnight UTC. Cached briefly; 0 if it cannot be read."""
    if time.monotonic() - _budget_cache["at"] < BUDGET_CACHE_SECONDS:
        return _budget_cache["value"]
    total = 0.0
    try:
        rows = _client().table(TABLE).select("cost_usd").gte("created_at", _start_of_today_utc()).execute().data
        total = float(sum(float(r["cost_usd"] or 0) for r in rows))
    except Exception as exc:
        logger.warning("llm.budget_unreadable | reason=%s", safe_error(exc, 160))
    _budget_cache.update(at=time.monotonic(), value=total)
    return total


def ensure_within_budget() -> None:
    """Refuses new paid work once today's estimated spend reaches DAILY_LLM_BUDGET_USD."""
    limit = settings.DAILY_LLM_BUDGET_USD
    if limit and spent_today_usd() >= limit:
        logger.error("llm.daily_budget_reached | limit_usd=%s", limit)
        raise PropertySystemException(
            "The daily processing limit has been reached. New work resumes tomorrow, or ask an admin to raise the limit.",
            status_code=429,
        )


# ---- dashboard aggregates -----------------------------------------------------

def summarize(rows: List[Dict[str, Any]], days: int, case_names: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Pure aggregation of llm_usage rows for the admin usage screen."""
    case_names = case_names or {}
    by_day: Dict[str, Dict[str, float]] = {}
    by_kind: Dict[str, Dict[str, float]] = {}
    by_case: Dict[str, float] = {}
    failures: List[Dict[str, Any]] = []
    totals = {"cost": 0.0, "calls": 0, "tokens_in": 0, "tokens_out": 0, "errors": 0, "rate_limited": 0}

    for row in rows:
        cost = float(row.get("cost_usd") or 0)
        t_in, t_out = int(row.get("tokens_in") or 0), int(row.get("tokens_out") or 0)
        day = str(row.get("created_at", ""))[:10]
        kind = row.get("kind") or "unknown"
        status = row.get("status") or "ok"

        totals["cost"] += cost
        totals["calls"] += 1
        totals["tokens_in"] += t_in
        totals["tokens_out"] += t_out
        d = by_day.setdefault(day, {"cost": 0.0, "calls": 0})
        d["cost"] += cost
        d["calls"] += 1
        k = by_kind.setdefault(kind, {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost": 0.0, "errors": 0})
        k["calls"] += 1
        k["tokens_in"] += t_in
        k["tokens_out"] += t_out
        k["cost"] += cost
        if status != "ok":
            k["errors"] += 1
            totals["rate_limited" if status == "rate_limited" else "errors"] += 1
            failures.append({"created_at": row.get("created_at"), "kind": kind, "status": status, "error": row.get("error")})
        if row.get("case_id"):
            by_case[str(row["case_id"])] = by_case.get(str(row["case_id"]), 0.0) + cost

    today = datetime.now(timezone.utc).date()
    series = []
    for offset in range(days - 1, -1, -1):
        date = (today - timedelta(days=offset)).isoformat()
        entry = by_day.get(date, {"cost": 0.0, "calls": 0})
        series.append({"date": date, "cost_usd": round(entry["cost"], 4), "calls": int(entry["calls"])})
    failures.sort(key=lambda f: str(f["created_at"]), reverse=True)
    return {
        "days": days,
        "estimated": True,
        "total_cost_usd": round(totals["cost"], 4),
        "total_calls": totals["calls"],
        "tokens_in": totals["tokens_in"],
        "tokens_out": totals["tokens_out"],
        "errors": totals["errors"],
        "rate_limited": totals["rate_limited"],
        "by_day": series,
        "by_kind": sorted(
            (
                {
                    "kind": name,
                    "calls": int(v["calls"]),
                    "tokens_in": int(v["tokens_in"]),
                    "tokens_out": int(v["tokens_out"]),
                    "errors": int(v["errors"]),
                    "cost_usd": round(v["cost"], 4),
                }
                for name, v in by_kind.items()
            ),
            key=lambda item: -item["cost_usd"],
        ),
        "top_cases": [
            {"case_id": case_id, "name": case_names.get(case_id), "cost_usd": round(cost, 4)}
            for case_id, cost in sorted(by_case.items(), key=lambda item: -item[1])[:10]
        ],
        "recent_failures": failures[:15],
    }


def load_summary(days: int) -> Dict[str, Any]:
    since = (datetime.now(timezone.utc) - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    client = _client()
    rows = (
        client.table(TABLE)
        .select("created_at,kind,model,tokens_in,tokens_out,cost_usd,status,error,case_id")
        .gte("created_at", since.isoformat())
        .order("created_at", desc=True)
        .limit(20000)
        .execute()
        .data
    )
    case_ids = list({str(r["case_id"]) for r in rows if r.get("case_id")})
    names: Dict[str, str] = {}
    if case_ids:
        for case in client.table("cases").select("id,property_name").in_("id", case_ids).execute().data:
            names[str(case["id"])] = case.get("property_name")
    summary = summarize(rows, days, names)
    summary["today_cost_usd"] = round(spent_today_usd(), 4)
    summary["daily_budget_usd"] = settings.DAILY_LLM_BUDGET_USD
    return summary
