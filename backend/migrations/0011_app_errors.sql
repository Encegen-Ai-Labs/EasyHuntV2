-- Server errors, copied from the log with secrets removed, so an admin can read
-- them without server access. One row per error-level log line. No document text.
create table if not exists app_errors (
    id          uuid primary key default gen_random_uuid(),
    created_at  timestamptz not null default now(),
    event       text,
    message     text not null,
    logger      text,
    exception   text,
    request_id  text,
    user_id     uuid,
    case_id     uuid,
    document_id uuid
);
create index if not exists app_errors_created_at_idx on app_errors (created_at desc);
alter table app_errors enable row level security;
