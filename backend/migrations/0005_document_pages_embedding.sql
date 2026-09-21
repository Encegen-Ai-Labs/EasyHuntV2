-- Same caveat as 0001-0004: run this manually against the Supabase project
-- (SQL Editor / psql), nothing in this repo/environment can run it for you.
-- This one also depends on 0001 (document_pages must already exist).
--
-- Semantic search: embeddings are generated per page by
-- app/services/embedding_service.py (Gemini's gemini-embedding-001, 768
-- dimensions — confirmed working against the live API; the more commonly
-- referenced "text-embedding-004" 404s on this API version/project, so don't
-- switch to it without re-checking), populated during the pipeline right
-- after document_pages rows are inserted (see pipeline_service.py). The RPC
-- function below exists because pgvector's distance operators (<=>) aren't
-- reachable through supabase-py's REST filter DSL — only via .rpc().

create extension if not exists vector;

alter table document_pages
    add column if not exists embedding vector(768);

-- ivfflat needs at least some rows to build meaningful clusters; lists=100 is
-- a reasonable default for a table this shouldn't grow enormous either way.
-- Safe to create even on an empty table.
create index if not exists idx_document_pages_embedding
    on document_pages using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

create or replace function match_document_pages(
    query_embedding vector(768),
    match_document_ids uuid[],
    match_count int default 20
)
returns table (
    id uuid,
    document_id uuid,
    page_number int,
    original_text text,
    english_text text,
    similarity float
)
language sql stable
as $$
    select
        document_pages.id,
        document_pages.document_id,
        document_pages.page_number,
        document_pages.original_text,
        document_pages.english_text,
        1 - (document_pages.embedding <=> query_embedding) as similarity
    from document_pages
    where document_pages.document_id = any(match_document_ids)
      and document_pages.embedding is not null
    order by document_pages.embedding <=> query_embedding
    limit match_count
$$;
