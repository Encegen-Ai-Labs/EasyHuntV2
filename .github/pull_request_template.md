## What and why


## Checked
- [ ] Tests added or updated, and CI is green
- [ ] No keys, passwords or client data in the code, logs or screenshots
- [ ] Anything that turns an error into text for a user or the database goes through `redact()` / `safe_error()`
- [ ] A new model or API call goes through `LlmCall` / `generate_tracked` so its cost is recorded
- [ ] A new database change is a numbered file in `backend/migrations/` and is safe to run twice
- [ ] A new setting is in `backend/.env.example` (name and a placeholder only)

## After merge
<!-- Anything to run or rebuild: a migration, `docker compose up -d --build`, a new secret to set -->
