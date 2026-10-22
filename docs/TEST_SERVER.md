# Putting the backend on a test machine (for team and load testing)

Simplest path: no registry, no GitHub deploy secrets. The machine builds the image itself from the repo.
This is for testing. Production still goes through `docs/CICD.md`.

## What the machine needs
- Windows 10/11 Pro or Linux, 8 GB RAM minimum (16 GB better), 20 GB free disk, always on, reachable by the team on the network.
- Docker Desktop (Windows, WSL2 backend) or Docker Engine + Compose v2 (Linux).
- Git.

## Steps (do these on the machine, e.g. over UltraViewer)
1. Start Docker and wait until `docker info` works.
2. `git clone https://github.com/Encegen-Ai-Labs/<repo>.git EasyHuntV2` then `cd EasyHuntV2` and `git checkout dev`
   (or the branch you want tested; see "Which branch" below).
3. Create `backend/.env` from `backend/.env.example` and fill in real values:
   - `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`
   - `GEMINI_API_KEY` (and `GOOGLE_TRANSLATE_API_KEY` if translating)
   - `APP_JWT_SECRET`: a long random string
   - `CORS_ORIGINS`: the address the frontend is opened from, e.g. `http://192.168.1.50:3000`
   - Keep `APP_ENV` as `development` for a test box, or `production` if you want the strict startup checks
     (it then refuses placeholder secrets and localhost CORS).
   - Set `DAILY_LLM_BUDGET_USD` low while load testing so a runaway test cannot burn money.
4. Apply any new `backend/migrations/*.sql` in the Supabase SQL editor, in order (the pipeline does not do this).
5. `docker compose up -d --build` (first build takes several minutes: LibreOffice + OCR packs).
6. Check: `docker compose ps` (api healthy), then open `http://localhost:8000/health/ready`; it should say `ok`.
7. Windows firewall: allow inbound TCP 8000 so teammates can reach `http://<machine-ip>:8000`.

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
No automatic migrations (needs the base schema in the repo) and frontend hosting undecided. The base image is pinned to a digest and containers have memory limits (redis 256m, api 2g, worker 4g).
Dependencies are now pinned in `backend/requirements.lock` (the image installs from it); `requirements.txt` lists what
we ask for, `requirements-dev.txt` adds pytest for CI. To upgrade a library, edit `requirements.txt`, then regenerate the
lock inside `python:3.11-slim` with `pip install -r requirements.txt && pip freeze`.
