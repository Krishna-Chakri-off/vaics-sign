# Setup
## Requirements
Python 3.12+, Node 20+, PostgreSQL 15+ (SQLite works for dev/tests). Optional: LibreOffice (Office→PDF), ClamAV, S3/MinIO.
## Backend
1. `cd backend && pip install -r requirements.txt`
2. `cp .env.example .env`, then set `SECRET_KEY` (the app refuses to start in `ENV=production` with a weak or default key), `DATABASE_URL=postgresql+psycopg2://user:pass@host/db` and `AUTO_CREATE_TABLES=false`.
3. `alembic upgrade head`
4. `python -m app.seed` seeds the plans. `DEMO_PASSWORD=... python -m app.seed --demo` also adds the demo users platform@, krishna@, sender@, auditor@ and templates@example.com.
5. `uvicorn app.main:app --port 8000 --proxy-headers`. Background jobs (reminders, expiry, billing, retention): set `RUN_SCHEDULER=true` on exactly one instance, or run `python -m app.jobs` from cron.
## Frontend
`cd frontend && npm ci && npm run build` produces `dist/`. Serve it with nginx (`frontend/nginx.conf` proxies `/api` to the backend). `VITE_API_URL` defaults to `/api/v1`.
## Email (Amazon SES)
Set `SMTP_HOST=email-smtp.<region>.amazonaws.com` and SMTP_USER/SMTP_PASSWORD from a secret manager. Leave SMTP_HOST empty to use the dev outbox.
## Docker
`docker compose up --build`. Profiles: `--profile s3` (MinIO) and `--profile av` (ClamAV). This has not been executed here (no Docker); only the YAML was validated.
