# Environment variables

Source of truth: `backend/app/core/config.py` (Settings). `backend/.env.example` is generated from it and contains placeholders only. Never commit real values; use a secret manager.

| Variable | Example / default | Notes |
|---|---|---|
| `ENV` | `development` |  |
| `APP_NAME` | `VAICS Sign` |  |
| `DATABASE_URL` | `sqlite:///./vaics_sign.db` |  |
| `SECRET_KEY` | `<secret>` | secret, set via secret manager |
| `PUBLIC_APP_URL` | `http://localhost:5175` |  |
| `PUBLIC_API_URL` | `http://localhost:8000` |  |
| `CORS_ORIGINS` | `http://localhost:5175,http://127.0.0.1:5175` |  |
| `CORS_ORIGIN_REGEX` | `http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+):\d+` |  |
| `AUTO_CREATE_TABLES` | `true` |  |
| `RUN_SCHEDULER` | `false` |  |
| `SCHEDULER_INTERVAL_SECONDS` | `300` |  |
| `SESSION_IDLE_MINUTES` | `30` |  |
| `SESSION_ABSOLUTE_HOURS` | `12` |  |
| `LOGIN_MAX_FAILURES` | `5` |  |
| `LOGIN_LOCK_MINUTES` | `15` |  |
| `EMAIL_TOKEN_HOURS` | `` | secret, set via secret manager |
| `RESET_TOKEN_MINUTES` | `` | secret, set via secret manager |
| `INVITE_DAYS` | `7` |  |
| `HIBP_CHECK` | `false` |  |
| `BRAND_PRODUCT_NAME` | `VAICS Sign` |  |
| `BRAND_ORG_NAME` | `VAICS Consulting` |  |
| `BRAND_PRIMARY` | `#0D47A1` |  |
| `BRAND_ACCENT` | `#E6007E` |  |
| `BRAND_LOGO_URL` | `/vaics-logo-full.png` |  |
| `MAX_DOC_MB` | `25` |  |
| `MAX_ENVELOPE_MB` | `100` |  |
| `MAX_DOCS_PER_ENVELOPE` | `50` |  |
| `SOFFICE_PATH` | `soffice` |  |
| `CLAMD_HOST` | `` |  |
| `CLAMD_PORT` | `3310` |  |
| `STORAGE_BACKEND` | `local` |  |
| `STORAGE_DIR` | `./storage` |  |
| `S3_BUCKET_IN` | `` |  |
| `S3_BUCKET_EU` | `` |  |
| `S3_BUCKET_US` | `` |  |
| `S3_REGION_IN` | `ap-south-1` |  |
| `S3_REGION_EU` | `eu-central-1` |  |
| `S3_REGION_US` | `us-east-1` |  |
| `S3_ENDPOINT_URL` | `` |  |
| `S3_OBJECT_LOCK_DAYS` | `0` |  |
| `LINK_EXPIRY_DAYS` | `120` |  |
| `ACCESS_CODE_LENGTH` | `6` |  |
| `CODE_MAX_ATTEMPTS` | `5` |  |
| `ACCESS_CODE_EXPIRY_HOURS` | `72` |  |
| `OTP_MINUTES` | `10` |  |
| `SIGNER_SESSION_MINUTES` | `30` |  |
| `SMTP_HOST` | `` |  |
| `SMTP_PORT` | `587` |  |
| `SMTP_USER` | `<ses-smtp-username>` |  |
| `SMTP_PASSWORD` | `<secret>` | secret, set via secret manager |
| `SMTP_FROM` | `no-reply@example.com` |  |
| `SMTP_SSL` | `false` |  |
| `EMAIL_ATTACH_MAX_MB` | `9` |  |
| `SMS_PROVIDER` | `dev` |  |
| `TWILIO_ACCOUNT_SID` | `` |  |
| `TWILIO_AUTH_TOKEN` | `` | secret, set via secret manager |
| `TWILIO_FROM` | `` |  |
| `MSG91_AUTH_KEY` | `` | secret, set via secret manager |
| `MSG91_TEMPLATE_ID` | `` |  |
| `SEAL_CERT_P12_PATH` | `` |  |
| `SEAL_CERT_P12_PASSWORD` | `` | secret, set via secret manager |
| `SEAL_TSA_URL` | `` |  |
| `SEAL_DEV_SELF_SIGNED` | `true` |  |
| `ESIGN_ESP_URL` | `` |  |
| `ESIGN_ASP_ID` | `` |  |
| `DSC_PROVIDER_URL` | `` |  |
| `QTSP_PROVIDER_URL` | `` |  |
| `RATE_LIMIT_ENABLED` | `true` |  |
| `RATE_LIMIT_PUBLIC_PER_MIN` | `120` |  |
| `RATE_LIMIT_AUTH_PER_MIN` | `<secret>` | secret, set via secret manager |

Compose-level (`/.env.example`): POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, PUBLIC_APP_URL, DEMO_PASSWORD, MINIO_ROOT_PASSWORD.
Frontend build: `VITE_API_URL` (default `/api/v1`).
Tests: `TEST_DATABASE_URL` (optional Postgres).
