-- Same caveat as 0001-0003: run this manually against the Supabase project,
-- nothing in this repo/environment has DB access to run it.
--
-- app/services/review_service.py's submit_document_review() (backing
-- PATCH /api/v1/review/documents/{id}, the Review Workspace's Approve/Flag for
-- correction buttons) writes review_notes onto the extractions row alongside
-- validated_json_output/reviewed_by/reviewed_at/status. The rest of those
-- columns already exist on the live extractions table (confirmed via a direct
-- schema probe) — review_notes is the one column that was never added, which
-- made every review submission fail with a 500 (postgrest PGRST204: "Could not
-- find the 'review_notes' column of 'extractions' in the schema cache").

alter table extractions
    add column if not exists review_notes text;
