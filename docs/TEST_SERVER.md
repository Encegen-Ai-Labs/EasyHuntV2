# Putting the backend on a test machine (for team and load testing)

Simplest path: no registry, no GitHub deploy secrets. The machine builds the image itself from the repo.
This is for testing. Production still goes through `docs/CICD.md`.

## What the machine needs
- Windows 10/11 Pro or Linux, 8 GB RAM minimum (16 GB better), 20 GB free disk, always on, reachable by the team on the network.
- Docker Desktop (Windows, WSL2 backend) or Docker Engine + Compose v2 (Linux).
- Git.

## Steps (do these on the machine, e.g. over UltraViewer)
1. Start Docker and wait until `docker info` works.
2. `git clone https://github.com/Encegen-Ai-Labs/EasyHuntV2.git` then `cd EasyHuntV2` and `git checkout dev`.
3. Create `backend/.env` from `backend/.env.example` and fill in real values:
   - `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`
   - `GEMINI_API_KEY` (and `GOOGLE_TRANSLATE_API_KEY` if translating)
   - `APP_JWT_SECRET`: a long random string
   - `DATABASE_URL`: Supabase Postgres connection string (Session pooler or Direct). This is what makes
     migrations automatic. If migrations 0001-0011 were already run by hand, run once:
     `docker compose run --rm migrate python -m scripts.migrate --baseline 11`
   - `CORS_ORIGINS` is not needed for the website (same address), only for other callers.
   - Set `DAILY_LLM_BUDGET_USD` low while load testing.
4. `docker compose up -d --build` (first build takes several minutes).
   Order: redis, then `migrate` (applies new `backend/migrations/*.sql`, then exits), then api + worker, web, proxy.
   If a migration fails, api/worker do not start: read `docker compose logs migrate`.
5. Open `http://localhost/` (or `http://<machine-ip>/`). One address serves the website and `/api/*`.
   Backend check: `http://localhost/health/ready` should say `ok`.
6. Windows firewall: allow inbound TCP 80 (and 8000 if load testing the API directly).

The database's base schema (the `documents` table etc.) is not in the repo: the Supabase project must already have it.
A migration that fails is rolled back completely and retried on the next start.

## Load testing
`cd backend && python scripts/load_test.py --help` (run from any machine that can reach the server).
Note from earlier work: the load test has only been run against a stub, not the live stack. Expect to tune.
Watch `docker compose logs -f api worker` and `docker stats` while it runs.

## Update / stop
- Update: `git pull && docker compose up -d --build`
- Logs: `docker compose logs --tail=100 api worker`
- Stop: `docker compose down`

## Which branch
Branch does not matter to Docker; it runs whatever is checked out. In this repo's pipeline:
- `dev` deploys to **staging** (the right place for team testing and load tests),
- `main` deploys to **production** and waits for a human approval.
So everything staying on `dev` is fine and intended. Merge to `main` only when you want a production release.
The latest work lives on `feature/multiuser-marathi-ui`; open a PR into `dev` (CI runs) before the test box pulls `dev`,
or check that branch out directly on the box for a quick first run.

## Known gaps before real production
The base database schema is not in the repo (migrations assume it exists). For HTTPS on a real domain, put the domain in `Caddyfile` instead of `:80`. The base image is pinned to a digest and containers have memory limits (redis 256m, api 2g, worker 4g).
Dependencies are now pinned in `backend/requirements.lock` (the image installs from it); `requirements.txt` lists what
we ask for, `requirements-dev.txt` adds pytest for CI. To upgrade a library, edit `requirements.txt`, then regenerate the
lock inside `python:3.11-slim` with `pip install -r requirements.txt && pip freeze`.
