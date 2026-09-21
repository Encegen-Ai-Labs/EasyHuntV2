-- Phase 5 of the pivot: translation. Same caveat as 0001_document_pages.sql —
-- this repo has no migration tooling, run this manually against the Supabase
-- project (SQL Editor / psql). Nothing in the codebase can run it for you.
--
-- Populated by PipelineService.execute_analysis_pipeline() via
-- translation_service.py, run against each page's original_text right after
-- page_extraction_service.py produces it (same pipeline step, before the rows
-- are inserted — see pipeline_service.py). Search (Phase 6) reads both this
-- column and original_text so a keyword matches regardless of which language it
-- was typed in.

alter table document_pages
    add column if not exists english_text text;
