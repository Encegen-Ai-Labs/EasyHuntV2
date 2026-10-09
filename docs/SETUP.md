# EasyHuntV2 setup

This guide runs the Next.js frontend on Windows and the API, Redis, and Celery
worker with Docker Compose. Supabase remains a hosted dependency; Compose does
not start a local Supabase instance.

## Prerequisites

- Docker Desktop installed and running with its Linux container engine.
- Node.js and npm installed.
- A configured Supabase project with the schema and Storage buckets expected by
  the application.
- Supabase credentials. Gemini and Google Translate API keys are needed for
  the corresponding document extraction, embeddings, and translation features.

## Configure the backend

From the repository root in PowerShell:

```powershell
Copy-Item backend\.env.example backend\.env
notepad backend\.env
```

Replace the sample values with your actual credentials, including
`SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and
`SUPABASE_JWT_SECRET`. Set the admin credentials as appropriate. Add
`GEMINI_API_KEY` and `GOOGLE_TRANSLATE_API_KEY` to enable those integrations.
Do not commit `backend/.env` or share its secret values.

Docker Compose loads `backend/.env` into both the API and worker. It overrides
the Celery broker and result-backend addresses inside the containers to use the
Compose Redis service. A repository-root `.env` is not required for these
services.

## Start the API, Redis, and worker

In the repository root:

```powershell
docker compose up --build -d
docker compose ps
```

The API is available at `http://localhost:8000`; its OpenAPI page is
`http://localhost:8000/docs`. The default Celery worker processes up to three
documents at once (`CELERY_WORKER_CONCURRENCY`, hard-capped at 6 in
`app/tasks/celery_app.py`). Each document also runs up to four pages
concurrently, so worst-case simultaneous Gemini calls are
workers x concurrency x 4 (12 by default). Consider provider limits before
raising it. Documents that Gemini rate-limits are retried automatically with
exponential backoff.

Useful operations:

```powershell
docker compose logs -f api worker
docker compose restart api worker
docker compose up --build -d api worker
docker compose down
```

The `up --build` command rebuilds the backend image before starting/recreating
the specified services. Use it after backend code changes. `docker compose
down` stops the services but keeps the Redis data volume. Avoid `docker compose
down -v` unless you intentionally want to delete that volume.

Docker Desktop must remain running while these services are in use.

## Start the frontend

Open a second PowerShell window:

```powershell
cd Frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The frontend uses `http://localhost:8000/api/v1`
by default. The frontend is not part of the Compose stack; `npm run dev` picks
up frontend code edits automatically.

## Local backend without Celery

For local backend development without the Docker queue, run the API with the
project's Python environment and keep `CELERY_ENABLED=false`. The existing
FastAPI background-task processing path is used in that mode. Do not enable
Celery locally unless Redis and at least one Celery worker are also running and
reachable by the API.

## Verify a real worker (first-time check)

Nobody had built this stack before it was added, so run through this once on a
new machine. Use real keys in `backend/.env`.

1. `docker compose config` should print the merged file with no error.
2. `docker compose build`, then `docker compose up -d redis api worker`.
3. `docker compose ps`: `redis` should be `healthy`, `api` and `worker` `running`.
4. `docker compose exec redis redis-cli ping` should print `PONG`.
5. `docker compose logs worker` should show `celery@... ready` and, under
   `[tasks]`, `documents.process`. It should also show `concurrency: 3`.
6. In the app, upload five or more documents to a case. In
   `docker compose logs -f worker`, expect lines like
   `Task documents.process[...] received` and then `succeeded`, with up to
   three running at once. The Documents list should move each file from
   `uploaded` to `processing` to `llm_done` without a page refresh.
7. **Outage test:** `docker compose stop redis`, then upload one document. It
   must not stay in `processing` forever: the upload response carries a warning,
   the upload panel shows an amber banner, the API log has an error line
   starting `documents.QUEUE_UNAVAILABLE_FALLING_BACK_IN_PROCESS`, and the
   document is processed inside the API container instead.
   Then `docker compose start redis` and confirm the next upload is queued again.

If the API log shows `QUEUE_UNAVAILABLE_*` in production, Redis or the worker is
down and the API process is doing the processing itself. Treat it as an alert.

## Troubleshooting

- **Docker cannot connect to `dockerDesktopLinuxEngine`:** start Docker Desktop
  and wait for its Linux engine to be ready, then check `docker version` for
  both Client and Server sections.
- **`supabase_url is required`:** confirm `backend/.env` exists and contains a
  real, non-empty `SUPABASE_URL`; then recreate the services with
  `docker compose up --build --force-recreate`.
- **Documents remain queued or processing:** check `docker compose ps` and
  `docker compose logs -f worker api`. Confirm Redis is healthy and the worker
  is running.
- **Frontend cannot reach the backend:** confirm the API is published on port
  8000 and that the frontend is configured to use `http://localhost:8000`.
