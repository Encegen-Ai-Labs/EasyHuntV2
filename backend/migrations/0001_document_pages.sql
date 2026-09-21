-- Phase 4 of the vendor-removal / manual-report-builder pivot: page-level extraction.
--
-- This repo has no migration tooling (no Alembic, no Supabase CLI project, no other
-- .sql files) — the existing schema lives entirely in the hosted Supabase project's
-- dashboard/SQL editor, outside version control. Run this manually against that
-- project (SQL Editor, or `psql`/`supabase db execute`) — nothing in this codebase
-- can run it for you.
--
-- One row per physical page of a document. Populated by
-- PipelineService.execute_analysis_pipeline() via page_extraction_service.py,
-- right after the existing whole-document extraction step. For single-page
-- documents (images, 1-page PDFs) this reuses that step's `full_text` — no extra
-- Gemini call. For multi-page PDFs, each page is rasterized and transcribed with
-- its own call, so page_number is true by construction (we choose which raster
-- image is "page N"), not something the model self-reports.
--
-- `english_text` (Phase 5 / translation) is intentionally NOT added here — that
-- column lands in a follow-up migration once the translation provider is chosen.

create table if not exists document_pages (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references documents(id) on delete cascade,
    page_number integer not null,
    original_text text,
    created_at timestamptz not null default now(),
    unique (document_id, page_number)
);

create index if not exists idx_document_pages_document_id on document_pages (document_id);
