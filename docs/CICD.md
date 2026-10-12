# CI/CD: how a change gets from your laptop to the lawyers

CI means "check every change automatically". CD means "ship a checked change automatically, safely, and be able to undo it". Both are GitHub Actions files in `.github/workflows/`. Nothing here needs a paid service.

## Why we have it

Until now the only safety was whoever remembered to run the tests. With five lawyers on real client documents, a bad change must be caught before it is merged and undone in minutes if it slips through. CI catches it before merge. CD makes every deploy the same boring, repeatable steps instead of someone typing commands on a server, and makes "go back to yesterday's version" one command.

## The picture

```
 feature branch ──push──▶ Pull request into dev ──▶ CI runs (5 checks) ──▶ review ──▶ merge to dev
                                                                                          │
                                       Deploy workflow: build image ──▶ deploy to STAGING ┘
                                                                                          │
              Pull request dev ──▶ main ──▶ CI again ──▶ review ──▶ merge to main         │
                                                                                          ▼
                       Deploy workflow: build image ──▶ WAIT for a human to approve ──▶ deploy to PRODUCTION
                                                                                          │
                                   server runs deploy.sh: new version up ──▶ is it ready? ──▶ yes: done
                                                                                          └──▶ no: previous version put back
```

## CI: `.github/workflows/ci.yml`

Runs on every pull request into `dev` or `main`, and on every push to them. Five jobs run side by side:

| Job | What it does | Blocks the merge? |
|---|---|---|
| **Backend tests** | installs the backend, runs all the Python tests with **fake credentials and no network to Supabase or Gemini** | Yes |
| **Frontend checks and build** | type check, unit tests, production build | Yes (lint is report-only for now) |
| **Backend image builds and starts** | builds the Docker image, checks no `.env` file is inside it, starts it and calls `/health` | Yes |
| **Secret and dependency scan** | `gitleaks` reads the whole git history for keys and passwords; `pip-audit` and `npm audit` list known-vulnerable libraries | The secret scan blocks; the audits only report |
| Lint (inside the first two) | style and unused-code checks | No, report-only until the existing warnings are cleaned |

The fake credentials matter: a test that accidentally reaches the real database or model fails here, instead of spending money or touching client data.

## CD: `.github/workflows/deploy.yml`

Runs when something is merged into `dev` or `main`.

1. **Build and publish the image.** The backend image is built and pushed to GitHub's container registry (`ghcr.io`), tagged with the commit id (for example `3f9a1c2b7d40`). The commit id is the version number; we never deploy "latest", so you always know exactly what is running.
2. **Deploy**, only if a server is configured. `dev` goes to *staging*, `main` goes to *production*. The production job **pauses until a named person approves it** in GitHub. It copies `deploy/deploy.sh` and the compose files to the server and runs the script.
3. **`deploy/deploy.sh` on the server:** remembers the running version, pulls the new image, restarts the API and worker, then waits up to two minutes for `/health/ready` (which checks the database and the queue). If it never becomes ready, it **automatically puts the previous version back** and the workflow shows red.

Until the server variables below exist, step 2 prints "no server configured" and stops. It is safe to merge this before any server is set up; you simply get a published image.

## How to use it day to day

1. Branch from `dev`: `git checkout dev && git pull && git checkout -b feature/what-you-are-doing`.
2. Push and open a pull request into `dev`. Fill in the checklist that appears.
3. Watch the **Checks** at the bottom of the PR. Green ticks: ready for review. A red cross: click **Details** to read the failing step. Fix, push again, the checks re-run by themselves.
4. After review, merge. The image is built and (once a server exists) staging updates.
5. When staging looks right, open a PR from `dev` into `main`. After it merges, go to **Actions → Deploy → the running job → Review deployments → Approve** to release to production. Deploy outside lawyers' working hours and tell them first.

Run the same checks yourself before pushing: `cd backend && python -m pytest -q` and `cd Frontend && npx tsc --noEmit && npm test && npm run build`.

## Roll back

On the server, in the app folder: `sh deploy.sh "$(cat .last_good_tag)"` returns to the last version that was ready, or give any older commit id (the images stay in the registry). Takes about a minute. Database changes are **forward only**: only add columns and tables, and remove or tighten things in a later release, so an older image still works against the newer database.

## One-time setup (when you get a server)

1. **Repository settings → Branches:** protect `dev` and `main`: require pull requests, require the CI checks (`Backend tests`, `Frontend checks and build`, `Backend image builds and starts`, `Secret and dependency scan`), require one review, no direct pushes.
2. **Settings → Environments:** create `staging` and `production`. On `production` add **Required reviewers** (yourself and one other person).
3. **On the server:** install Docker, make a folder (say `/opt/easyhunt`), put the real `backend/.env` there as `backend/.env` (never in git), and put a reverse proxy (Caddy or nginx) in front for HTTPS. Create a dedicated user whose only job is deploying.
4. **In each GitHub environment:** add variables `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`, `DEPLOY_KNOWN_HOSTS` (the output of `ssh-keyscan <host>`), and the secret `DEPLOY_SSH_KEY` (a private key made just for this; add its public half to the deploy user's `authorized_keys`). Use a different key per environment.
5. **Make the package readable by the server:** the first time, on the server run `docker login ghcr.io` with a read-only token.
6. Set `APP_ENV=production` in the server's `.env`. The API then refuses to start on placeholder secrets, an open CORS list or localhost origins (see `docs/OPERATIONS.md`).

## What is deliberately not here yet

- **Database migrations are not run by the pipeline.** Apply `backend/migrations/*.sql` by hand first (Supabase SQL editor); automatic migrations need the base schema in the repo (BACKLOG).
- **No frontend image or hosting.** The frontend is built and tested in CI; where it is served from (Vercel or the same server) is still an open decision in `docs/PRODUCTION_PLAN.md`.
- **Action versions use major tags** (`@v4`), kept current by Dependabot, rather than pinned commit ids.
