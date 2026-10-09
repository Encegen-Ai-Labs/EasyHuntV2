-- Same caveat as 0001-0008: run this manually against the Supabase project.
--
-- DO NOT APPLY until this query returns no rows (it finds documents that
-- ended up with more than one extractions row, which the pipeline's
-- check-then-insert can produce when /process and the batch path run for the
-- same document at once):
--
--     select document_id, count(*), array_agg(id order by created_at)
--     from extractions group by document_id having count(*) > 1;
--
-- If it returns rows, decide per document which row to keep (the one a
-- reviewer edited, if any) and delete the others yourself first. This file
-- never deletes anything: it stops with an error if duplicates remain.

do $$
begin
    if exists (select 1 from extractions group by document_id having count(*) > 1) then
        raise exception 'extractions still has duplicate document_id rows; resolve them first';
    end if;
end $$;

alter table extractions
    add constraint extractions_document_id_key unique (document_id);
