-- One row per call to a paid model or API (Gemini, Cloud Translation): what it
-- was for, how many tokens (or characters) went in and out, an estimated cost,
-- how long it took and whether it worked. Never holds document text.
create table if not exists llm_usage (
    id          uuid primary key default gen_random_uuid(),
    created_at  timestamptz not null default now(),
    kind        text not null,            -- page_transcription, field_extraction, embedding, translation, report_autofill, ...
    model       text not null,
    tokens_in   integer,                  -- characters for kind = translate_google
    tokens_out  integer,
    cost_usd    numeric(12, 6) not null default 0,
    estimated   boolean not null default false,  -- true when the provider gave no token count
    latency_ms  integer,
    status      text not null default 'ok',      -- ok | error | rate_limited
    error       text,                            -- short, secret-free description
    case_id     uuid,
    document_id uuid,
    user_id     uuid,
    request_id  text
);

create index if not exists llm_usage_created_at_idx on llm_usage (created_at desc);
create index if not exists llm_usage_case_idx on llm_usage (case_id);
create index if not exists llm_usage_document_idx on llm_usage (document_id);

-- Only the backend (service role) reads or writes this; the public API key cannot.
alter table llm_usage enable row level security;
