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
documents at once. Page-level processing can add further concurrency, so
consider provider limits before increasing worker capacity.

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
cd C:\Users\AAAA\Desktop\ai-property\EasyHuntV2\Frontend
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
