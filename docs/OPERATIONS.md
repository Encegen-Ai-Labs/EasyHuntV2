# Operations: logging, cost, limits and secrets

How the running system tells you what it is doing and protects itself. Built from the plan in `docs/PRODUCTION_PLAN.md` (sections 6 and 8).

## 1. Secrets: where they live and how they are kept out of sight

| Secret | Lives in | Never in |
|---|---|---|
| `GEMINI_API_KEY`, `GOOGLE_TRANSLATE_API_KEY`, Supabase keys, `APP_JWT_SECRET`, `SENTRY_DSN` | `backend/.env` on the machine (and the server's `.env`) | git, the Docker image, the browser, logs, error messages |

What enforces that:

- **`.gitignore`** excludes every `.env*` file except `.env.example` (placeholders only). CI runs `gitleaks` over the full history on every pull request. History was checked on 2026-10-12: no real key was ever committed.
- **The Docker image never contains `.env`**: it is passed in at run time (`env_file`), and CI fails if one is found inside the image.
- **The browser only ever receives the API address.** No secret has a `NEXT_PUBLIC_` name.
- **`app/core/redaction.py`**: every exception that becomes text (a stored page message, an API error, a log line, a traceback) is passed through `redact()`/`safe_error()`. It removes the *actual values* of the configured secrets and the usual key shapes (`?key=…`, `Bearer …`, JWTs, `AIza…`, `AQ.…`, `sk-…`). The logger redacts every line, so a forgotten call site still cannot print a key.
- **The Translation key travels in a header, not the URL.** The original leak: an HTTP error message contains the full URL, and the URL had `?key=<key>`, so a failed translation saved the key into the page text and showed it on screen.
- **Unexpected errors show the user a generic message and a reference id**, never the exception.
- **Separate login-token secret.** Set `APP_JWT_SECRET` (long random value). Otherwise login tokens are signed with the Supabase JWT secret, which also grants database access.
- **Production refuses to start unsafe** (`APP_ENV=production`): placeholder or short secret, no `APP_JWT_SECRET`, `CORS_ORIGINS` open or on localhost, `ADMIN_PASSWORD` left in the environment, rate limiting off. Elsewhere the same problems are logged as warnings at start-up.
- **Sentry (if enabled) receives stack traces only**: request bodies, headers, cookies, query strings and user details are stripped before sending.

**If a key has been exposed, rotate it** (create a new one, put it in `.env`, restart, delete the old one). The Translation key in this project was shown on screen and stored in one page's text; the stored copy was scrubbed on 2026-10-12, but treat that key as exposed.

### Rotating a key
1. Create the new key in Google Cloud / Supabase. 2. Edit `backend/.env`. 3. `docker compose up -d` (restart picks it up). 4. Disable the old key. 5. Check `/health/ready` and one translation.

## 2. Logs

- Every log line is a single line. In `staging`/`production` (or `LOG_FORMAT=json`) it is **JSON** with: time, level, event, message, `request_id`, `user_id`, `case_id`, `document_id` and every `key=value` from the message as its own field.
- Every response carries `X-Request-ID`. When a lawyer reports a problem, ask for the reference shown in the error (or find the request id) and search the logs for it: you get everything that request did, including the model calls.
- The access log line has method, path, status, duration and user id. **No request bodies, no document text** are logged.
- Docker keeps 5 files of 10 MB per container (`docker-compose.yml`), so logs cannot fill the disk. Read them with `docker compose logs -f api` or `docker compose logs api | grep <request-id>`.

## 2b. Server errors in the admin screen

Every error-level log line is also saved (secrets removed) in the `app_errors` table: when, what, the request reference, and which user, case and document it was for. Admins read the latest 50 under **Usage → Recent server errors**. The container log remains the full record; this list exists so a failure is visible without server access and survives a container being replaced. If the database cannot be reached the record is dropped rather than slowing a request.

Uploads: a file that fails is kept on the upload screen with its reason and a **Retry** button. A dropped connection to storage is retried automatically (3 attempts) before the file is reported as failed. The first such failure seen (2026-10-12, 1 of 7 files) was `SSLV3_ALERT_BAD_RECORD_MAC`, a garbled connection while uploading to Supabase Storage; it is most likely the shared connection being used by several threads at once, and the retry covers it. If it keeps happening, give storage uploads their own client.

## 3. Model cost and tokens

Every call to Gemini or Google Translation is recorded in the `llm_usage` table: what it was for, tokens in and out, **estimated cost**, how long it took, and whether it worked or was rate-limited. No document text is stored.

- **See it:** sign in as an admin → **Usage** in the top bar. Today's spend, the last 7 or 30 days, cost per task, the most expensive cases, and recent failures.
- **Costs are estimates.** Google does not return a price per call. We multiply tokens by the prices in `.env` (`LLM_PRICE_*`, `TRANSLATE_PRICE_PER_M_CHARS`). **Check those numbers against Google's price list for the model in use**, and compare the 30-day total with the Google Cloud billing page. A failed or rejected call counts as zero.
- **Daily limit:** set `DAILY_LLM_BUDGET_USD` (0 = none). When today's estimate reaches it, new uploads, translations and report drafts answer "daily processing limit reached" and resume tomorrow; work already running finishes. Also set a **budget alert in Google Cloud Billing** as the independent backstop.
- Rate-limited (429) calls are counted separately on the Usage screen. Many of them mean lowering `CELERY_WORKER_CONCURRENCY` or raising Google's quota, not more retries.

## 4. Rate limiting

| Where | Limit (default) | Counted per |
|---|---|---|
| Login | 10 / minute | client address (stops password guessing) |
| Upload | 20 / minute | user |
| Translate, process, report draft and export | 20 / minute | user (these spend money or CPU) |
| Everything else | 300 / minute | client address (not `/health`) |

Change them with `RATE_LIMIT_*` in `.env`. A blocked request gets HTTP 429 with a `Retry-After` header and a plain message. Limits are shared across API processes through Redis. If Redis is unreachable, requests are **allowed** and the problem is logged (a broken limiter must not lock lawyers out). Set `TRUST_PROXY=true` only behind a reverse proxy you control, so the real client address is used.

## 5. Health

- `/health`: the process is up.
- `/health/ready`: the database and (when the queue is on) Redis answer. 503 with which part is down, no details. The deploy script and an uptime monitor should use this one.

## 6. Do we need a dashboard? Grafana?

**Not Grafana yet.** Recommendation, in order of when it pays off:

1. **Now: the Usage screen in the app** (built). Cost, tokens and failures are the questions you will actually ask during the pilot, and the data is already in your database. No extra service to run or secure.
2. **Before real client data: Sentry** (free tier): set `SENTRY_DSN`. It emails you the moment an unexpected error happens, with the stack trace, and groups repeats. This is the "find out before the lawyers do" tool. Plus a free uptime monitor (UptimeRobot or Better Stack) on `/health/ready`.
3. **Later, if you ever need to search many days of logs:** ship the JSON logs to **Grafana Cloud's free tier** (Loki) with Grafana Alloy or Promtail. The logs are already in the right shape, so this is configuration, not code. Self-hosting Grafana, Loki and Prometheus on the same small server is not worth the upkeep for five users.

## 7. Known gaps (also in BACKLOG)

- The login token is kept in the browser's `localStorage`. A cookie that scripts cannot read (httpOnly) is safer against injected scripts; that is a larger change.
- No Content-Security-Policy header yet (needs the real production addresses).
- No audit trail of who viewed or exported which client record.
- Two database functions (`match_document_pages`, `extraction_corrections_no_update`) have a mutable `search_path`, and the `vector` extension is in the `public` schema (Supabase advisor warnings, low risk).
