-- Phase 1 of the SOP-realignment round (docs/ROADMAP.md): distinguishes
-- risk_flags raised by structural chain analysis (chain_service.py /
-- risk_service.py — survey-number conflicts, chain gaps, insufficient
-- history) from risk_flags raised by the extraction LLM actually reading a
-- document's dispute/litigation/encumbrance language (llm_extractor.py's
-- new red_flags field, persisted in pipeline_service.py). Same table, same
-- API (app/api/v1/flags.py) — just tagged with provenance so the lawyer can
-- tell the two apart.
--
-- As with every other migration in this directory, the base risk_flags
-- table lives only in the hosted Supabase project — apply this manually via
-- the SQL Editor before Phase 1 code runs against a real database.

alter table risk_flags add column if not exists source text not null default 'structural';
