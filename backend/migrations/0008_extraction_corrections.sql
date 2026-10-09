-- Same caveat as 0001-0007: run this manually against the Supabase project,
-- nothing in this repo/environment has DB access to run it.
--
-- Append-only record of every change a reviewer makes to an extraction (and
-- to a page's text), plus a `confirm` row for each field left unchanged when
-- a document is approved. Backs app/services/corrections_service.py.
--
-- The app treats a failed write here as non-fatal (the review save itself
-- still succeeds; the response says corrections were not recorded), so
-- applying this late loses history for the saves made before it exists, but
-- never blocks a lawyer.
--
-- Apply order for this series: 0007_extraction_cache.sql, then this file,
-- then (only if the duplicate check in docs/EXTRACTION_QUALITY.md 8.3 comes
-- back clean) 0009_extractions_unique_document.sql.

create table if not exists extraction_corrections (
    id               uuid        primary key default gen_random_uuid(),
    created_at       timestamptz not null default now(),

    -- Plain ids, deliberately NOT foreign keys: deleting a document (which
    -- deletes its extraction) must not be blocked by, or erase, its history.
    extraction_id    uuid,
    document_id      uuid        not null,
    case_id          uuid,

    -- 'owner_name', 'chain[1].date', 'red_flags[0]', 'page[3].original_text'
    field_path       text        not null,
    change_type      text        not null
                     check (change_type in ('edit', 'clear', 'add', 'remove', 'confirm')),
    original_value   jsonb,      -- what the model produced
    previous_value   jsonb,      -- what was there just before this save
    corrected_value  jsonb,      -- what the reviewer saved

    reason           text
                     check (reason is null or reason in ('misread', 'wrong_field', 'hallucinated', 'format', 'other')),

    corrected_by     uuid,
    revision         integer     not null default 1,  -- one per save of an extraction

    -- context at the time, for grouping errors by cause later
    model_used       text,
    handwriting      boolean,
    model_confidence text,
    grounding_status text        -- reserved; filled once grounding checks exist
);

-- A retried save reuses its revision and cannot insert the same row twice.
create unique index if not exists extraction_corrections_revision_field_uidx
    on extraction_corrections (extraction_id, revision, field_path)
    where extraction_id is not null;

create index if not exists extraction_corrections_document_idx
    on extraction_corrections (document_id);

-- Append-only: rows can be inserted, not changed. (Deleting stays possible so
-- an erasure request for a client's data can still be honoured.)
create or replace function extraction_corrections_no_update() returns trigger as $$
begin
    raise exception 'extraction_corrections is append-only';
end;
$$ language plpgsql;

drop trigger if exists extraction_corrections_no_update on extraction_corrections;
create trigger extraction_corrections_no_update
    before update on extraction_corrections
    for each row execute function extraction_corrections_no_update();

-- Rows hold client data. Give this table the same access rules as `extractions`.
