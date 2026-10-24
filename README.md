# VAICS Sign

Internal e-signature service for VAICS Consulting staff and the people they send documents to. FastAPI + PostgreSQL backend, React (Vite) frontend.
It runs as a single VAICS organisation: staff join by invitation from an administrator, and every feature (templates, bulk send, in-person signing,
parallel routing, groups, branding, reports) is available to VAICS users according to their role, with no plans, quotas or billing.
Signers must accept the electronic-records disclosure and affirm a signature-intent statement (with its meaning: Approved, Reviewed, …), both
recorded in the audit trail. A privacy notice is at `/privacy`; staff can request a copy or deletion of their own data from My account
(admin-approved under Privacy & retention).

**Signature flow (preserved from v2):** Signer 1 = VAICS representative, Signer 2 = countersigner, strict order. Each invitation emails the signing link, and the access code goes in a *separate* email. Every signature requires a reason. The stamp shows the signature, name, reason, IST and UTC time, and a SHA-256 field hash. The completed, sealed PDF and the Certificate of Completion are sent to all parties.

## Quick start (dev)
```bash
# backend
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env            # fill SECRET_KEY etc. Defaults: SQLite + dev outbox (no real email)
alembic upgrade head && DEMO_PASSWORD='<choose>' python -m app.seed --demo
uvicorn app.main:app --reload --port 8000
# frontend
cd ../frontend && npm ci && npm run dev    # proxies /api to :8000
```
Docker: `cp .env.example .env` (fill it in), then `docker compose up --build` → http://localhost:8080. Note: the compose file has only been checked for syntax; it was not run in this build environment because Docker was unavailable.

Docs: [SETUP](docs/SETUP.md) · [ARCHITECTURE](docs/ARCHITECTURE.md) · [ENVIRONMENT_VARIABLES](docs/ENVIRONMENT_VARIABLES.md) · [API](docs/API.md) · [DEMO_GUIDE](docs/DEMO_GUIDE.md) · [FRS_TRACEABILITY](docs/FRS_TRACEABILITY.md) · [SECURITY](docs/SECURITY.md)

## Tests
`cd backend && pytest -q` (SQLite). Set `TEST_DATABASE_URL=postgresql+psycopg2://...` to run against Postgres. CI (`.github/workflows/ci.yml`) runs both, plus Alembic up/check/down and the frontend build.

## Honest status
In dev, email and SMS go to an outbox that you can view in the UI; nothing is delivered. The UI never claims delivery. Aadhaar eSign, DSC, QES and ID verification are interfaces only. They refuse with "not configured" and never report false success. The completed-PDF seal uses a dev self-signed certificate unless a real PKCS#12 is configured. Per-requirement status is in FRS_TRACEABILITY.md.
