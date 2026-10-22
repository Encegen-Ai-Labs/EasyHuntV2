"""Apply backend/migrations/NNNN_*.sql to the database, once each, in order.

    python -m scripts.migrate              apply what has not been applied yet
    python -m scripts.migrate --baseline 11   record 0001..0011 as already applied (they were run by hand)

Needs DATABASE_URL: the Postgres connection string (Supabase: Project Settings -> Database ->
"Session pooler" or direct connection, not the transaction pooler). Applied files are listed in the
table schema_migrations. Each file runs in one transaction, so a failing file changes nothing and
the next start retries it. Without DATABASE_URL it does nothing, loudly.
"""
import os
import sys
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"
LOCK_ID = 727_001  # arbitrary; stops two containers migrating at once


def files() -> list[Path]:
    return sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def main(argv: list[str]) -> int:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("migrate: DATABASE_URL is not set, skipping. New migrations will NOT be applied.", file=sys.stderr)
        return 1 if os.environ.get("APP_ENV") == "production" else 0

    import psycopg

    baseline = int(argv[argv.index("--baseline") + 1]) if "--baseline" in argv else 0
    with psycopg.connect(url, autocommit=True, prepare_threshold=None) as conn:
        conn.execute("select pg_advisory_lock(%s)", (LOCK_ID,))
        conn.execute("create table if not exists schema_migrations (name text primary key, applied_at timestamptz not null default now())")
        done = {row[0] for row in conn.execute("select name from schema_migrations")}
        pending = 0
        for path in files():
            if path.name in done:
                continue
            if int(path.name[:4]) <= baseline:
                conn.execute("insert into schema_migrations (name) values (%s)", (path.name,))
                print(f"migrate: {path.name} recorded as already applied")
                continue
            pending += 1
            print(f"migrate: applying {path.name}")
            sql = path.read_text(encoding="utf-8-sig")
            try:
                with conn.transaction():
                    conn.execute(sql)
                    conn.execute("insert into schema_migrations (name) values (%s)", (path.name,))
            except Exception as exc:
                print(f"migrate: {path.name} FAILED, nothing from it was kept: {exc}", file=sys.stderr)
                return 1
        print(f"migrate: up to date ({pending} applied now)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
