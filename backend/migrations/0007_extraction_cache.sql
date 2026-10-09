-- Same caveat as 0001-0006: run this manually against the Supabase project,
-- nothing in this repo/environment has DB access to run it.
--
-- Backs app/services/extraction_cache.py. Until this is applied, leave
-- EXTRACTION_CACHE_ENABLED unset/false (the default): the app then never
-- touches this table. After applying it, set EXTRACTION_CACHE_ENABLED=true.
--
-- Apply order for this series: 0007 (this file), then 0008_extraction_corrections.sql.

create table if not exists extraction_cache (
    -- sha256(content_sha256 | model | pipeline_version): see extraction_cache.make_key
    key              text primary key,
    content_sha256   text        not null,   -- sha256 of the uploaded file's bytes
    model            text        not null,
    pipeline_version text        not null,   -- computed hash of prompts + pipeline code/config
    result           jsonb       not null,   -- {routed_pages, extracted, model_used}
    created_at       timestamptz not null default now()
);

-- Look up / clean up every entry for one file regardless of version.
create index if not exists extraction_cache_content_sha256_idx
    on extraction_cache (content_sha256);

-- Entries contain the document's transcribed text. Give this table the same
-- access rules as `extractions` (no row level security is enabled here
-- because the live policies for the other tables are not recorded in this
-- repo; match whatever `extractions` uses).
