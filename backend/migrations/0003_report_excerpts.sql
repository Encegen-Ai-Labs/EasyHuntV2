-- Phase 8 of the pivot: manual report builder. Same caveat as 0001/0002 — run
-- this manually against the Supabase project, nothing in this repo can run it.
--
-- The `reports` table already has schema drift between two existing write paths
-- (report_draft_service.py's LLM-draft flow uses llm_draft+status; report_service.py's
-- PDF-summary flow uses file_path+generated_by — see project notes). Rather than
-- add a THIRD undistinguished write path to the same ambiguity, this migration
-- adds a `report_type` column so all three stay distinguishable. Both older flows
-- keep working completely unmodified; this feature's rows always get 'manual'.

alter table reports
    add column if not exists report_type text not null default 'legacy';

-- Best-effort backfill so pre-existing rows aren't stuck as 'legacy' forever.
-- Neither older flow reads report_type, so an imperfect backfill is harmless.
update reports set report_type = 'llm_draft' where llm_draft is not null and report_type = 'legacy';
-- The live table's PDF-summary column is actually named pdf_path, not
-- file_path (report_service.py/report_repo.py/api/v1/reports.py all had this
-- wrong — fixed alongside this migration; confirmed by inspecting the real
-- table's columns rather than trusting the old code/docs).
update reports set report_type = 'pdf_summary' where pdf_path is not null and report_type = 'legacy';

create table if not exists report_excerpts (
    id uuid primary key default gen_random_uuid(),
    report_id uuid not null references reports(id) on delete cascade,
    document_id uuid not null references documents(id) on delete cascade,
    page_number integer not null,
    excerpt_text text not null,
    sequence_order integer not null,
    note text,
    created_at timestamptz not null default now()
);

create index if not exists idx_report_excerpts_report_id on report_excerpts (report_id);
