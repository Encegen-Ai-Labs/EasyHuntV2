# Production plan

Status: proposal, 2026-10-09. Nothing here is implemented. Written from the repo only: no `.env` was read and Supabase was not contacted, so anything about the live project (region, plan, RLS state, bucket settings) is marked **verify**.

Target: a small pilot, about 5 lawyers, one lawyer per account, accounts created by an admin, holding bank client documents.

Costs are rough 2026 list-price estimates in USD, to be re-checked on the vendors' pricing pages before anyone commits. Gemini usage is excluded from the totals; see section 6.

## What the repo tells us (findings that shape the plan)

These come from reading the code and drive several recommendations below.

1. **The base schema is not in the repo.** `backend/migrations/0001`–`0009` only add `document_pages`, `report_excerpts`, `extraction_cache`, `extraction_corrections` and columns. `users`, `cases`, `documents`, `extractions`, `risk_flags`, `reports` and the storage buckets were created by hand. A staging or disaster-recovery environment cannot be rebuilt from the repo today. This is the first thing to fix (section 5).
2. **The backend uses the service-role key for all data access** (`get_supabase_key()` prefers `SUPABASE_SERVICE_ROLE_KEY`), which bypasses RLS. Authorization is done in application code (`authorize_case_access`, `RoleRequirement`). RLS is therefore defence in depth, not the access control; the app code is.
3. **Auth is the app's own**, not Supabase Auth: `users.hashed_password` (argon2), JWTs minted by `create_access_token`, signed HS256 with `SUPABASE_JWT_SECRET`. The same secret signs app tokens and is the Supabase project's JWT secret, so a leak of one is a leak of both.
4. **CORS is `allow_origins=["*"]` with `allow_credentials=True`** (`app/main.py`).
5. **`/health` is shallow** (returns ok without touching Supabase or Redis). The worker has no health check.
6. **Uploads are stored at `cases/{case_id}/{file_name}` with `x-upsert: true`.** Two files with the same name in one case silently overwrite each other in storage while both rows survive. This is a data-integrity bug and matters for a legal record.
7. **Only PDF, PNG, JPEG are accepted, 10 MB max** (`doc_service.py`). Rasterization is PyMuPDF for PDFs and Pillow for images (`page_extraction_service.rasterize_pages`).
8. **Document content leaves the country.** Page images and text go to the Gemini API, and page text goes to Google Cloud Translation. Hosting the app in Mumbai does not change that. This is the biggest residency question (section 1).
9. **No token or cost accounting exists** for Gemini (no `usage_metadata` reads). Logging is plain text to stdout.
10. **Frontend has no Dockerfile**, and `NEXT_PUBLIC_API_URL` is read at build time, so each environment needs its own build.
11. `requirements.txt` is unpinned (`>=`), so two builds a week apart can differ.
12. The admin create-reviewer response echoes the plaintext password (already in BACKLOG.md).

---

## 1. Hosting

### Recommendation

One small VM in **AWS Mumbai (ap-south-1)** running the whole stack with Docker Compose behind Caddy (automatic HTTPS), and **Supabase Pro in the Mumbai region**. No Kubernetes, no managed container platform for the pilot.

| Piece | Where | Rough monthly |
|---|---|---|
| API + Celery worker + Redis + Next.js frontend | 1 VM, 2 vCPU / 8 GB, 50 GB disk (EC2 `t3.large` class, or Lightsail equivalent), Mumbai | $60–75 |
| Supabase (Postgres, Storage, daily backups) | Pro plan, Mumbai | $25 (+ compute add-on if the default is too small) |
| Domain, DNS | any registrar | $1–2 |
| Error monitoring, uptime check | free tiers (section 6) | $0 |
| Off-site backup bucket (section 7) | S3 Mumbai | $1–3 |
| **Total excluding Gemini** | | **about $90–110 (roughly ₹7.5–9k)** |

### Why

- **Single VM** because 5 users do not need horizontal scale, and the stack is already four containers in `docker-compose.yml`. A VM keeps cost predictable and debugging simple (`docker compose logs`). Its weakness is that it is one machine; mitigated by section 3 (queue durability), section 4 (rollback in minutes) and section 7 (rebuild from scratch is documented and rehearsed).
- **8 GB, not 4 GB,** because the worker runs OpenCV, Tesseract and PyMuPDF, and each document fans out to up to 4 concurrent pages of large PNGs (a single oversized page was measured at 44 MB after enhancement per the comments in `page_extraction_service.py`). Concurrency 2–3 on 4 GB risks OOM kills. Start at 8 GB; if memory stays under 50% after a month, drop to 4 GB.
- **Not Vercel for the frontend** to keep one place to operate and one set of network paths to the API, and because India-region guarantees for serverless functions are less clear than a VM we pick the region of. Vercel is a fine later move if the frontend needs it; it changes nothing in the backend plan.
- **Not Render/Railway/Fly** because their India presence is limited or absent; the residency requirement is the deciding factor, not price.
- **Not Azure/GCP** only because AWS Mumbai is the simplest known quantity here and both Supabase and the VM sit in the same region (low latency, no cross-region egress). Azure Central India or GCP `asia-south1` are equivalent if a bank requires one of them.
- The Supabase project must be in the same region as the VM. **Verify the existing project's region.** A Supabase project cannot change region in place: moving means a new project, a dump/restore of Postgres, and a copy of storage objects. Better to learn that now than after go-live.

### Network layout

- Caddy is the only thing listening publicly (80/443). API binds to `127.0.0.1:8000`, frontend to `127.0.0.1:3000`, Redis has no published port. Today `docker-compose.yml` publishes `8000:8000` to all interfaces; change that for production.
- Two hostnames, e.g. `app.<domain>` (frontend) and `api.<domain>` (API), so CORS can be locked to exactly one origin.
- SSH via key only, or SSM Session Manager with no port 22 open. Security group: 80/443 in, nothing else.
- OS patching: unattended security upgrades on; monthly reboot window agreed with the lawyers.

### Data residency: what to check with the boss or the banks

Ask these as written questions and keep the answers:

1. Does the bank's outsourcing/IT policy require that client documents **stay in India at rest**, or also **in processing**? (RBI's outsourcing and data-localisation expectations differ for payment data vs. general bank records; the bank's own vendor-risk team will state its rule. Do not assume.)
2. Is **sending page images and text to Google's Gemini API** acceptable? The Gemini Developer API does not promise India processing. The options if the answer is no or "only in India": **Vertex AI in `asia-south1` (Mumbai)** with the Gemini models available there, an enterprise agreement and zero-data-retention terms, or a different extraction approach for that bank. This is a code change in `llm_extractor.py` / `page_extraction_service.py` / `embedding_service.py` (SDK supports both), so decide early. **Verify model availability and data-processing terms on Google's current Vertex documentation.**
3. Same question for **Google Cloud Translation** (`translation_service.py`). Cloud Translation has regional endpoints; or translation could be done by the same model in the same call.
4. Does the paid Gemini tier's terms stop **training on our data** (they should; confirm in the contract we actually have, not the marketing page)?
5. Does a bank require an **audit right, a data-processing agreement, a pen-test report, or ISO 27001/SOC 2** from us or from our subprocessors (Supabase, AWS, Google)? Supabase and AWS publish SOC 2 reports; ask the bank what it accepts.
6. Who is the **data controller**: the bank, the lawyer's firm, or Encegen? This decides who can instruct deletion (section 7) and who is liable in a breach. India's DPDP Act obligations follow from this answer; get legal advice, not an engineer's reading.
7. Maximum **retention** the bank allows or requires, and whether deletion on request must be provable.
8. Breach notification window the bank expects from us.

If any answer is "India-only processing", the plan changes in two places: Gemini moves to Vertex Mumbai, and Translation uses a regional endpoint or goes away. Everything else is unaffected.

---

## 2. Docker for production

Current state: `backend/Dockerfile` is single-stage `python:3.11-slim`, installs six Tesseract language packs, installs unpinned requirements, copies `app`, `migrations`, `templates`, and already drops to a non-root `app` user (uid 1000). `.dockerignore` excludes `.env`. That is a reasonable base. The changes below are small.

### Backend image

- **Size:** expect roughly 1.2–1.6 GB (OpenCV, NumPy, PyMuPDF, Tesseract with six packs). Multi-stage builds would save little because most weight is runtime libraries. Don't chase size; chase reproducibility. Measure it in CI and fail the build if it grows more than, say, 25% between PRs (catches accidental dependency additions).
- **Pin dependencies.** Generate a lock (`pip-compile --generate-hashes` from a `requirements.in`, or `uv pip compile`) and install from it. Move `pytest` and `httpx` (test-only) out of the runtime file into `requirements-dev.txt`; the runtime image should not contain test tooling.
- **Pin the base image** by minor version and digest (`python:3.11.x-slim-bookworm@sha256:...`), updated deliberately.
- **Non-root:** already done; add `no-new-privileges` and drop all capabilities in compose (`cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`), and `read_only: true` with a `tmpfs: /tmp` (the pipeline writes temp files; confirm nothing else writes under `/app`).
- **Health checks:**
  - API: add `HEALTHCHECK` hitting a new `/health/ready` that checks Supabase reachability (one cheap query) and, when `CELERY_ENABLED`, Redis `PING`. Keep `/health` as the cheap liveness probe. (Do not make readiness call Gemini; that would burn quota and flap on Google incidents.)
  - Worker: `celery -A app.tasks.celery_app:celery_app inspect ping -d celery@$HOSTNAME` as the compose healthcheck.
  - Redis: already has one.
  - Frontend: `wget -qO- http://127.0.0.1:3000/` (or a `/healthz` route).
- **Graceful stop:** set `stop_grace_period` on the worker to something like 120 s so in-flight pages finish on a normal deploy. Tasks are `acks_late`, so a hard kill still re-delivers (section 3).
- **Ship migrations and templates in the image** (already done) but the app must not run migrations at start-up. Migrations are a separate deploy step (section 5).
- **Gunicorn/uvicorn workers:** `uvicorn` single process is fine for 5 users. Pipeline work is off in the worker once Celery is on. Revisit only if API latency shows up in monitoring.

### Frontend image

Create `Frontend/Dockerfile`: multi-stage, `output: "standalone"` in `next.config.mjs`, Node LTS slim, non-root `node` user, copy only `.next/standalone`, `.next/static`, `public`. `NEXT_PUBLIC_API_URL` is a **build arg** (it is inlined at build time), so the production image is built with the production API URL; do not reuse a dev image in production. Expect about 150–250 MB.

### Secrets handling

- **No `.env` in any image.** `backend/.dockerignore` already excludes `.env`; add `Frontend/.dockerignore` (`.env*`, `node_modules`, `.next`). Add a CI step that runs `docker run --rm <image> sh -c 'find / -name ".env*" -not -path "/proc/*" 2>/dev/null'` and fails if anything is found.
- Secrets are injected at **run time** as environment variables. `config.py` reads real environment variables ahead of the env file, so no code change is needed. Note that the `env_file` lookup in `config.py` resolves to `/.env` or `/app/.env` inside the container, neither of which should exist.
- **Pilot:** a root-owned, mode `0600` env file on the VM outside the repo (`/etc/easyhunt/api.env`) referenced by compose `env_file`. **Next step up:** AWS SSM Parameter Store (SecureString, free tier) fetched at deploy time into that file. Never put secrets in GitHub Actions logs; use GitHub Environments secrets only for the deploy SSH key and registry token, not the app's runtime secrets.
- Client-side keys: only `NEXT_PUBLIC_*` values may be public. Confirm nothing sensitive is prefixed that way.
- Rotate on a calendar and on every staff change: Supabase service-role key, JWT secret (see section 8), Gemini key, Translate key, admin password.
- Separate keys per environment (dev, staging, prod). A dev laptop must never hold the production service-role key.

---

## 3. Celery and Redis

### When to turn it on

**On in production from day one** (`CELERY_ENABLED=true`), off on laptops. Reason: with it off, document processing runs in the API process as a FastAPI background task, so every deploy or crash silently abandons whatever was processing and leaves documents stuck in `processing`. With 5 lawyers uploading 20-file batches during working hours, a routine deploy would hit that. D9 already built the safety net; the cost is one more container.

### Sizing

- **1 worker container, `CELERY_WORKER_CONCURRENCY=2`** at first. Worst case Gemini calls in flight = 1 × 2 × 4 pages = **8**. That is comfortably inside paid-tier limits for 5 users and keeps memory bounded (about 3–4 GB peak on the 8 GB VM).
- Scale by raising concurrency to 3 (the default; hard cap is 6 in code) before adding a second worker, and add a second worker container only when queue wait time (section 6) regularly exceeds a few minutes. Past the cap on one box, move the worker to its own VM; the broker URL is the only change.
- **Verify the real Gemini quota** for the project's tier; the in-flight arithmetic above is only safe if it is below the per-minute limit.

### How it fails safely

Already built (D9): `acks_late`, `worker_prefetch_multiplier=1`, retry with backoff on Gemini 429, fallback to the in-process path if the broker is down, documents flagged rather than left in `processing`. Remaining gaps to close for production:

1. **Redis persistence.** `redis:7-alpine` with only a volume uses RDB snapshots, so a crash can lose the last minutes of queued messages. Run `redis-server --appendonly yes --appendfsync everysec`. Bind to the internal Docker network only, and set a password (`requirepass`) included in `CELERY_BROKER_URL`.
2. **Visibility timeout vs. time limit.** With a Redis broker, an unacked message is redelivered after `visibility_timeout` (default 1 h). `task_time_limit` is also 3600 s, so a long task can be redelivered while still running, producing a duplicate. Set `broker_transport_options={"visibility_timeout": 7200}` (above the hard limit).
3. **Idempotency.** The `already_processed` guard stops duplicates but also causes the half-processed-after-crash case already in BACKLOG. Fix (clear partial rows or make steps resumable) before relying on redelivery.
4. **Stuck-document sweeper.** A small scheduled job (Celery beat or a cron container) that flags any document in `processing` for longer than the task time limit plus margin, and logs it. This is the backstop for anything not covered above.
5. **Worker memory.** `worker_max_tasks_per_child` (e.g. 50) and a container memory limit so a leak or a pathological PDF restarts the child instead of the box.
6. **Poison files.** Cap pages per document (a 600-page PDF within 10 MB is possible) and fail fast with a clear message. Add a page cap in `rasterize_pages`.
7. **No dead-letter queue needed at this scale.** After retries are exhausted the document becomes `flagged`, which the lawyer sees in the UI; the log line is the alert source.
8. **Redis down at 3 a.m.** Uploads fall back in-process (loud log); alert on the `QUEUE_UNAVAILABLE_*` log line (section 6).
9. **Complete the open item** in BACKLOG: the live Docker worker test (`docs/SETUP.md`, "Verify a real worker"). Do it on staging before production.

---

## 4. CI/CD

### On every pull request to `dev` (GitHub Actions)

`.github/workflows/ci.yml`, triggered on `pull_request` targeting `dev` and `main`, plus `push` to `dev`. Jobs run in parallel; all must pass to merge (branch protection on `dev` and `main`: required checks, no direct pushes, at least one review).

| Job | Steps |
|---|---|
| `backend` | Python 3.11, cache pip, install runtime + dev requirements, install `tesseract-ocr` system package if any test needs it, `ruff check backend` and `ruff format --check`, `pytest` from `backend/` (`pytest.ini` already points at `tests`). Run with **no secrets and no network** to Supabase/Gemini so a test that accidentally hits the live project fails visibly. |
| `frontend` | Node LTS, `npm ci` in `Frontend`, `npx tsc --noEmit`, `npm run lint`, `npm test` (vitest run), `npm run build` (catches build-only errors) |
| `docker` | Build backend and frontend images (no push), run the no-`.env`-in-image check, record image size, smoke test: start the backend image with dummy env and `curl /health` |
| `migrations` | Spin up a throwaway `pgvector/pgvector` Postgres service, apply the base schema snapshot plus all migrations in order, then apply them a second time to prove they are idempotent (see section 5) |
| `security` (non-blocking at first) | `pip-audit`, `npm audit --omit=dev`, `gitleaks` secret scan. Make blocking once the baseline is clean. |

Lint: the frontend has `eslint`; the **backend has no linter configured**, so add `ruff` with a minimal config and start non-blocking, fixing only new violations, to avoid a giant reformat PR. Dependabot for pip, npm, Docker base images and Actions, weekly.

Pin third-party actions to a full commit SHA. Give the workflow `permissions: contents: read` by default.

### Branches and deploy flow

`dev` is integration; `main` is production. Environments: **local**, **staging** (same VM layout but small, or a second compose project on a cheap VM; Supabase free-tier project is enough for rehearsal), **production**.

1. Feature branch → PR to `dev` → CI → review → merge. Merging to `dev` auto-deploys to **staging**.
2. When staging is verified (checklist in the PR), open a PR `dev` → `main`. CI runs again. A required reviewer approves the **`production` GitHub Environment** (manual approval gate).
3. On merge to `main`, the workflow:
   1. builds the backend and frontend images and tags them with the **git SHA** (and `latest` only for convenience, never deployed by tag `latest`),
   2. pushes to GHCR (free for private use at this scale) or ECR Mumbai,
   3. runs the **migration step** against production (section 5) and stops if it fails,
   4. SSHes to the VM (deploy key, restricted command) or uses SSM Run Command: `docker compose pull && docker compose up -d --remove-orphans`, with the image SHA in an env var,
   5. polls `/health/ready` for up to a couple of minutes; if it fails, **automatically reverts to the previous SHA**,
   6. posts the result.
4. Deploys avoid working hours; announce to the lawyers. Worker `stop_grace_period` keeps in-flight documents alive; anything else is re-queued (section 3).

### Rollback

- **Code:** redeploy the previous image SHA. Keep the last 5 SHAs on the VM and in the registry. Command in the runbook: `IMAGE_TAG=<sha> docker compose up -d`. Target time: under 5 minutes.
- **Database:** migrations are **forward-only**; there are no down-migrations. To make code rollback always safe, follow expand/contract: a release may add nullable columns/new tables, but a column is dropped or made `NOT NULL` only in a *later* release, after no deployed code depends on the old shape. Review checklist item on every migration PR.
- **Bad data change:** restore from backup (section 7). Take a manual backup (Supabase on-demand) immediately before any release containing a non-trivial migration.
- Feature flags already exist as env switches (`CELERY_ENABLED`, `EXTRACTION_CACHE_ENABLED`); prefer shipping risky behaviour dark and enabling it by env change, which is a restart, not a deploy.

---

## 5. Migrations

### Problem

`backend/migrations/*.sql` are numbered files pasted by hand into the Supabase SQL editor, with no record of which ones ran where, and the base schema is missing entirely (finding 1). Backlog items already depend on knowing what is applied ("confirming 0005 is applied").

### Recommendation

**Step A, one-off: capture the baseline.** Produce `0000_baseline.sql` from the live project's current schema (`pg_dump --schema-only --no-owner` of the `public` schema plus the bucket definitions and the `vector` extension) via the Supabase CLI or a local `pg_dump` against a **read-only connection the user runs themselves**. Review it by hand, strip Supabase-internal objects, and commit it. This lets CI and staging be built from the repo and makes disaster recovery real. (I was told not to connect to Supabase, so this is a task for the user, or for a later session with explicit permission.)

**Step B: a tracked, ordered runner.** Two good options; recommended is the first.

- **Recommended: a small in-repo runner**, `backend/scripts/migrate.py` (about 80 lines, `psycopg`):
  - table `schema_migrations(version text primary key, checksum text, applied_at timestamptz)`,
  - takes a Postgres connection string from `DATABASE_URL` (Supabase's direct or session-mode pooler connection; **not** the transaction pooler, which breaks advisory locks),
  - takes a `pg_advisory_lock` so two deploys cannot race,
  - applies files in lexical order, each inside one transaction together with its `schema_migrations` insert,
  - refuses to run if an already-applied file's checksum changed (no editing history),
  - `--dry-run` lists pending, `--status` lists applied vs. pending, and
  - treats the existing 0001–0009 as applied on first run via an explicit `--baseline-through 0009` flag (after the user confirms which are applied on each environment).
  - Keeps today's file names and the habit of `if not exists` / idempotent SQL, which the existing files already follow.
- **Alternative: Supabase CLI** (`supabase db push`) with files renamed to its timestamped format and `supabase migration repair` to mark history. It is standard and needs no custom code, but forces a rename of existing files and a `supabase/` directory layout, and it still needs the same baseline.

Either way:

- **Order and safety:** migrations run in the deploy workflow **before** the new containers start, against staging first (automatic) then production (after approval). CI applies the full chain to a throwaway Postgres twice. Take a Supabase backup immediately before production migrations.
- **No migration at app start-up.** Two containers starting at once would race and a failed migration would crash-loop the API.
- **Rules for authors:** additive first; `create ... if not exists`; no long-held locks (`create index concurrently` where needed, which cannot run in a transaction, so such files are flagged and run outside one); large backfills in separate batched jobs, not in the migration; every migration PR states its rollback plan.
- **Retire the SQL editor** for schema changes except in a declared emergency, and then back-port the SQL to a numbered file the same day.
- `optional_normalise_survey_number.sql` is not in the numbered chain; either number it or document that it is run manually and never by the runner. Decide as part of the survey-number backlog item.

---

## 6. Monitoring

Keep it to four things a part-time team will actually look at.

### Errors
- **Sentry** (free developer tier, or self-host later) in the backend (`sentry-sdk[fastapi,celery]`), worker and frontend (`@sentry/nextjs`). Scrub request bodies and headers; **never send document text, file names or party names to Sentry** (`send_default_pii=False`, a `before_send` that strips payloads). Send alerts to one email/WhatsApp-able channel.
- Alert rules: any unhandled exception in the pipeline, any `flagged` spike, any 5xx rate over a few percent for 5 minutes.

### Logs
- Convert logging to **structured JSON** (the existing `logger.info("pipeline.rasterized | document_id=%s ...")` convention is already key=value; a JSON formatter makes it searchable). Add a request-ID middleware so a lawyer's complaint maps to log lines.
- Docker `json-file` driver with `max-size`/`max-file` rotation so logs cannot fill the disk, shipped to **CloudWatch Logs (Mumbai)** or Grafana Cloud free tier. Retain 90 days; access logs for audit longer (section 8).
- **Never log document contents.** Audit the existing log lines for text fragments and extracted values before shipping logs anywhere.

### Uptime
- External check on `https://api.<domain>/health/ready` and the frontend URL every minute from outside the VM (UptimeRobot or Better Stack free tier), alerting on 2 consecutive failures. Plus a **dead-man's-switch** (Healthchecks.io) pinged by the stuck-document sweeper, so silence is itself an alert.
- VM metrics: CPU, memory, disk, via CloudWatch agent or `node_exporter`; alert at 80% disk and 85% memory.

### Gemini cost and rate-limit tracking
Nothing exists today (finding 9). Add:
- A single wrapper around the Gemini calls that records, per call: model, purpose (page transcription, structured extraction, embedding, translation), input/output token counts from `response.usage_metadata`, latency, status, and whether it was a 429/retry. Emit as a structured log line **and** insert into a new `llm_usage` table (`document_id`, `case_id`, `user_id`, `kind`, `model`, `tokens_in`, `tokens_out`, `latency_ms`, `status`, `created_at`; no content).
- A weekly SQL view/report: cost per document, per case, per lawyer, by model, using a price table kept in config. This is also how to answer "what does one title scrutiny cost us", which the pricing conversation with banks will need.
- **Budget guardrails:** a daily spend cap in config that, when reached, pauses *new* processing with a clear message rather than failing mid-document; an alert at 70% and 100% of the monthly budget; and a Google Cloud billing budget alert on the key's project as the independent backstop. The extraction cache (`EXTRACTION_CACHE_ENABLED`) directly reduces spend and should be enabled once migration 0007 is applied and verified.
- Rate-limit visibility: count 429s per hour and queue wait time (upload time to first `processing`). Sustained 429s mean lower concurrency or a higher quota tier, not more retries.

---

## 7. Backups, retention and deletion

### Backups
- **Postgres:** Supabase Pro includes daily backups (7-day retention on Pro; **verify current plan terms**). Point-in-time recovery is a paid add-on; for a legal-records product, turn it on once there is live client data and the cost is acceptable (re-check price). Add a **nightly `pg_dump` to an S3 Mumbai bucket** with a lifecycle rule (30–90 days) and server-side encryption, so we are not solely dependent on the vendor's backup, and so we hold an independent copy that can be restored into a fresh project.
- **Storage objects:** Supabase's database backups **do not include the contents of storage buckets**. This is the common trap. Run a nightly sync of the `documents` and `reports` buckets to the same S3 bucket (a small script using the Storage API with the service role from the VM, or `rclone` with Supabase's S3-compatible endpoint, **verify it is enabled**). Enable S3 versioning so an overwrite (finding 6) or deletion is recoverable.
- **Config/secrets:** the compose files and runbook live in git; the secret values live in the secrets store with their own backup. Losing the JWT secret invalidates all sessions, which is recoverable; losing the service-role key is a rotation, not data loss.
- **Restore drill:** before go-live and then quarterly, restore the latest dump and bucket copy into the staging project, point staging at it, and open a real case. A backup that has never been restored is not a backup. Record the elapsed time; that is the real RTO. Reasonable pilot targets: RPO 24 h (1 h with PITR), RTO 4 h.

### Retention and deletion of client documents
These need the bank's answers (section 1, questions 6–7). Proposed default to put in front of them:

- **Retention clock** starts when a case is closed; default retention a fixed period agreed with each bank (for example 7–8 years if a bank's record-keeping rules require it, otherwise as short as allowed). Make it a per-case/per-bank setting, not a constant.
- **Deletion on request** (bank or data principal, via the controller): a documented procedure and then an admin-only endpoint/script that removes, for a case: storage originals, the `enhanced/` page images, `document_pages` text and embeddings, `extractions`, `extraction_cache` rows keyed to those files (the cache stores extracted content of the same documents, so it must go too), `extraction_corrections`, `risk_flags`, `report_excerpts`, generated reports in the `reports` bucket, and signed URLs naturally expire (5–60 min). It writes a **deletion receipt** (what, when, by whom, counts) to an audit table that does not itself contain client data.
- **Backups and deletion:** deleted data persists in backups until they age out. State this in the policy (e.g. "removed from backups within 90 days by expiry") and keep backup retention at that figure; do not promise instant purge from backups. Get the bank to accept the wording.
- **Today's `delete_document`** removes the row and the storage file, but check that it also removes the `enhanced/` images, embeddings, cache and corrections rows. **Verify**; I did not trace every cascade.
- **Dev/staging must never contain real client documents.** Use synthetic documents only; the eval set (`backend/eval`) should be checked for real client data before it is ever shared or sent to a third party.
- Translated text and embeddings are derived client data and fall under the same retention and deletion rules.

---

## 8. Security basics

Ordered by value for effort.

### Fix before any real client document goes in
1. **Lock CORS** to the single frontend origin (`allow_origins=["https://app.<domain>"]`), explicit methods and headers. `*` together with `allow_credentials` is wrong.
2. **Separate the app JWT secret from Supabase's.** Introduce `APP_JWT_SECRET` (random, 64+ bytes) for `create_access_token` / `decode`. The Supabase project JWT secret should then be used by nothing in the app. Existing sessions are invalidated once; acceptable.
3. **Fix the same-name upload overwrite** (finding 6): store at `cases/{case_id}/{document_id}/{sanitised_name}` (or the id only) and drop `x-upsert`. Sanitise file names (no path separators or control characters).
4. **Stop echoing the plaintext password** from the create-reviewer response (already backlogged); send it out of band or make users set it on first login.
5. **Login hardening:** rate-limit `/auth/login` per IP and per account (e.g. `slowapi` or at Caddy), generic error messages (already), lockout/backoff after repeated failures. Shorten or add refresh tokens: 60-minute access tokens with no revocation means a stolen token lives an hour and a deactivated lawyer keeps access until expiry unless `get_current_user` re-checks `is_active` on every request. **Verify it does**; if not, add it.
6. **Upload validation beyond the declared MIME type:** check magic bytes, not the client's `Content-Type`; limit pages; the PDF parser (PyMuPDF) processes untrusted input, so keep it patched and run the worker unprivileged with the read-only filesystem described in section 2. This matters more once Word/Excel are added (section 9).
7. **Admin bootstrap:** `ADMIN_EMAIL`/`ADMIN_PASSWORD` in env should be used once to create the first admin and then removed from the environment. Require a strong password and make the admin change it.

### Auth and access control
- Authorization lives in the app because the service-role key bypasses RLS. Keep a test per endpoint proving a reviewer cannot read or write another reviewer's case, document, page, flag, correction, report or search results (several exist; make this a CI-enforced checklist). Cross-tenant leakage is the failure that ends the business.
- Search (`search_service`) and the `match` SQL function must filter by case/ownership; confirm they cannot return another lawyer's pages.
- Signed URLs are short-lived (300 s for pipeline, 3600 s for reports). Reduce the report URL to minutes, or stream through the API (backlog item) so no bearer-in-URL file token lands in history.
- Add MFA for admin accounts at minimum. Since auth is custom, this is app work (TOTP), not a Supabase toggle; flag it as a later phase if the banks require it.

### RLS
- Because the app uses the service role, **enable RLS on every table with no policies for `anon`/`authenticated`** ("deny by default"). Then a leaked **anon** key (which is exposed to browsers if the frontend ever uses it, and is in `.env.example` as `SUPABASE_KEY`) can read nothing. Check the live state: if any table has RLS off, the PostgREST endpoint exposes it to anyone holding the anon key. **Verify, as a first-day security task.** Do the same for storage buckets: private, no public policies.
- Write RLS for `authenticated` only if the browser ever talks to Supabase directly. Today it does not, so keep it denied.

### Secrets
- Covered in section 2. Additionally: secret scanning in CI (gitleaks), pre-commit hook locally, rotate anything that has ever been pasted into chat, a ticket, or committed.

### Access logs and audit trail
- Two different things: **operational logs** (section 6) and an **audit log** of who did what to which client record. Add an `audit_log` table (append-only; `user_id`, `action`, `entity`, `entity_id`, `case_id`, `ip`, `user_agent`, `created_at`, no document content) written on: login success/failure, case create/read/delete, document upload/view/download/delete, page-text edit, review save/correction, report generate/export, flag raise, admin account creation/deactivation, deletion-on-request. Retain at least as long as the strictest bank retention. The existing `extraction_corrections` table is append-only already and is a good model.
- Caddy access logs retained 12 months in S3, IPs included, as the independent record.

### Transport and platform
- TLS 1.2+ only (Caddy default), HSTS, and response headers on the frontend and API (`X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy` restricting to own origin, `frame-ancestors 'none'`).
- Disable `/docs` and `/openapi.json` in production (or put behind admin auth). `FastAPI(openapi_url=None)` when `ENV=production`.
- Encrypt the VM disk (EBS encryption) and the backup bucket. Supabase encrypts at rest by default.
- A short written **incident response** one-pager: who is told, in what order (the bank's timeline from section 1, question 8), how to rotate every secret, how to revoke all sessions.
- A **pen test or at least an external vulnerability scan** before the first bank signs off; some banks will ask for it anyway.

---

## 9. Word and Excel upload support

### What is needed

Currently `ALLOWED_MIMETYPES = pdf, png, jpeg` and the pipeline's first step is "rasterize to one PNG per page", after which each page goes through enhancement, router (OCR or VLM), translation, extraction and embedding. The least invasive design is to **keep that pipeline unchanged and add a conversion step that turns Word and Excel into the thing it already understands: a PDF (then pages).**

### Where it fits

```
upload  ->  validate (type, magic bytes, size)  ->  store original as-is
        ->  [NEW] normalise: .docx/.doc/.xlsx/.xls  --LibreOffice headless-->  PDF
        ->  rasterize_pages (existing)  ->  enhance -> route -> extract -> ...
```

- **Store the original** Word/Excel file exactly as uploaded (evidence), and store the **converted PDF alongside it** under the same document id (for example `.../converted.pdf`). The page viewer, highlighting and the existing `document_pages` model all work off pages, so they continue to work unchanged. Page numbers refer to the converted PDF; show that in the UI ("converted from Word").
- **Conversion tool:** LibreOffice in headless mode (`soffice --headless --convert-to pdf`). Adds about 400–600 MB to the image (install `libreoffice-writer` and `libreoffice-calc` only, not the full suite, plus fonts including **Noto Sans Devanagari, Tamil, Telugu, Kannada** so Indian-language text renders and is not boxes). Run it **in the worker only**, in a separate, tightly limited subprocess (timeout, memory limit, temp dir, no network, own user profile directory per run, because LibreOffice is not safe to run two instances against one profile).
- **Pure-Python alternative for text-heavy `.docx`:** `python-docx` can read text and tables directly and skip rasterization (and OCR cost). Faster and cheaper, but loses layout, headers/footers, stamps and embedded images, and the existing downstream steps expect page images and bounding boxes. Not recommended as the primary path; reasonable later as an optimisation for pure-text Word files.
- **Excel needs care.** A spreadsheet has no natural page boundary; LibreOffice will paginate by print range and can produce hundreds of pages or cut columns across pages. Decide print behaviour up front (fit width to one page, landscape, all sheets, hidden sheets skipped), cap total pages, and tell the user when a sheet was truncated. For title scrutiny, spreadsheets are most likely extracts, encumbrance listings and fee schedules; ask the lawyers which they actually have before investing in perfect Excel layout.

### Security (the part that is easy to underestimate)
- Office files are a classic malware vector. **Macros must never run** (`.docm`, `.xlsm`, `.xls` with VBA are rejected outright; LibreOffice configured with macros disabled), external links/OLE objects and remote images are not fetched (no network for the converter), and legacy binary `.doc`/`.xls` can be rejected in v1 and accepted later if lawyers need them.
- Validate by **magic bytes and structure** (a `.docx` is a ZIP containing `[Content_Types].xml` and `word/`), enforce **zip-bomb limits** (uncompressed size and entry count), a conversion timeout, and the existing size limit.
- Optionally run a ClamAV scan on every upload (it is useful for PDFs too). Cheap on a VM; adds a service.
- Password-protected or corrupt files must fail with a clear message, not hang the worker.

### Code touch-points (for a later implementation PR)
`ALLOWED_MIMETYPES` and the front-end file picker and accept list; a new `app/services/office_conversion.py`; a new branch at the top of `rasterize_pages` (or in `pipeline_service` right before it) selecting conversion by MIME type; extraction-cache key (hash of the original bytes, unchanged, but include the converter version in the pipeline version so a LibreOffice upgrade does not return stale results); page-viewer note; tests with small fixture files, including Marathi/Hindi text; Docker image change and size budget; worker memory limit. **No change** to routing, OCR, Gemini calls, embeddings, review, report builder, or schema other than a `source_format` / `converted_path` column on `documents`.

### Cost/effort
About 1–1.5 weeks including fixtures, Docker, tests and the UI note; Excel print-layout tuning is the unbounded part. Do Word first, Excel second.

---

## 10. Phased rollout

Smallest useful first. Each phase ends with a testable "done"; do not start the next until it is met.

### Phase 0: Know what we have (about 2–3 days)
Goal: no unknowns about the live system.
- Get the written answers to the residency/retention questions in section 1 (can run in parallel to everything).
- Capture `0000_baseline.sql`; confirm which of migrations 0001–0009 are applied; confirm the Supabase region and plan; check RLS state of every table and bucket (section 8).
- Confirm the Gemini tier and quota; confirm whether `delete_document` removes all derived data.
- **Done when:** a one-page "current state" note exists with the live region, applied migrations, RLS status and quotas, and the boss has the section 1 questions in writing.

### Phase 1: CI and a reproducible build (about 1 week)
Goal: every change is checked, every image is reproducible.
- GitHub Actions for backend tests, ruff, frontend tsc/lint/vitest/build, Docker build; branch protection on `dev` and `main`; pinned requirements; `requirements-dev.txt`; `Frontend/Dockerfile`; Dependabot.
- **Done when:** a PR to `dev` runs all jobs green in CI, a deliberately broken test blocks the merge, both images build in CI from a clean checkout, and the no-`.env`-in-image check passes.

### Phase 2: Safe schema management (about 3–5 days)
Goal: environments can be built and migrated from the repo.
- Baseline file, migration runner with tracking table, CI job that applies the chain twice to a throwaway Postgres, staging Supabase project built from the repo.
- **Done when:** a brand-new Supabase project is brought to the current schema with one command and the app passes a smoke test against it; production's tracking table matches reality; a re-run is a no-op.

### Phase 3: Security fixes that must precede real data (about 1 week)
Goal: close the items in section 8 "Fix before any real client document".
- CORS lock, separate app JWT secret, upload path fix, password echo, login rate limit, active-user check per request, docs disabled in prod, RLS deny-by-default confirmed, audit log table and writes.
- **Done when:** each item has a test or a verified check, a cross-reviewer access test suite passes, and an outside review (a colleague or a scan) finds no high-severity issue.

### Phase 4: Staging deployment (about 3–5 days)
Goal: the full stack running as it will in production, with synthetic data only.
- VM in Mumbai, Docker Compose with Caddy, Redis with AOF and password, Celery on, health checks, secrets from the root-owned env file, the staging Supabase project, deploy from `dev` via Actions with rollback.
- Run the live worker test from `docs/SETUP.md` and the long-outstanding hand verification of Phases 2–4 from DECISIONS.md.
- **Done when:** merging to `dev` deploys to staging automatically, a 20-file batch of synthetic documents completes through the worker, killing the worker mid-batch results in completion after restart, killing Redis results in a loud fallback and no stuck documents, and a deliberately bad release is rolled back in under 5 minutes.

### Phase 5: Observability and backups (about 1 week)
Goal: we find out before the lawyers do, and we can recover.
- Sentry, structured logs shipped and rotated, uptime checks, the stuck-document sweeper, the Gemini usage table and wrapper with a budget alert, nightly dump and bucket sync to S3, and **a restore drill**.
- **Done when:** a forced exception produces an alert within minutes, a stopped container pages someone, a week of Gemini spend is queryable per document, and the production-shaped backup has been restored into a fresh project and a case opened from it, with the elapsed time recorded.

### Phase 6: Production pilot (about 1 week to stand up, then 4–6 weeks of pilot)
Goal: 5 lawyers on real cases with a safety net.
- Production VM and Supabase (Mumbai), production deploy gate, accounts created by the admin, a one-page user guide, a runbook (deploy, rollback, restore, rotate, incident), agreed support hours, a weekly review of cost, errors and lawyer feedback.
- Start with one lawyer and a few real cases, add the others after a week without a serious incident. Keep the lawyers' reviewed corrections flowing into the evaluation set as already planned in `docs/EXTRACTION_QUALITY.md`.
- **Done when:** the pilot has run for two weeks with no data-integrity or access-control incident, restore drill repeated once, cost per case is known, and the lawyers' go/no-go is recorded.

### Phase 7: Pilot-driven additions (as justified by the pilot)
In rough order: Word support, then Excel; retention/deletion tooling with receipts; MFA for admins; Vertex AI Mumbai if the banks require in-India processing (this may move **up** to before Phase 6 if the answer in section 1 is "India-only"); streamed report export (BACKLOG); second worker or a larger VM; PITR.
- **Done when** each has its own acceptance test and the pilot lawyers have used it on a real case.

---

## Decisions needed from you

1. **Residency rule:** does the bank require India-only *processing* (not just storage)? If yes, Gemini moves to Vertex AI Mumbai and Translation changes; this alters the schedule. Who asks the banks, and by when? (Everything in section 1.)
2. **Cloud provider:** AWS Mumbai as proposed, or does the boss or a bank require Azure Central India / GCP `asia-south1`?
3. **Supabase region:** is the live project already in Mumbai? If not, accept a new project plus a data move now rather than later?
4. **Budget:** is about $90–110/month (excluding Gemini) acceptable for the pilot, and is a monthly Gemini cap needed (what number)?
5. **Who is the data controller** and who can instruct deletion? What is the retention period?
6. **Migration tool:** my in-repo runner (recommended) or the Supabase CLI?
7. **Permission for Phase 0:** may I (or you) run a read-only schema dump and RLS check against the live project, and in which session?
8. **Staging:** a second small VM plus a free Supabase project (recommended, about $15–25/month), or a staging compose on the same VM to save money (weaker isolation)?
9. **Breaking change in storage paths** (section 8, item 3): OK to change the storage path scheme and run a one-off migration of existing objects?
10. **Word/Excel priority:** do the lawyers need both before the pilot, or can Word follow the pilot and Excel wait for evidence of demand? Are legacy `.doc`/`.xls` required?
11. **Security extras for the banks:** will a pen test, MFA for admins, or SOC 2-style evidence be expected before sign-off? Who pays for the pen test?
12. **Support model:** who is on call for the pilot, in which hours, and how do the lawyers report problems?
