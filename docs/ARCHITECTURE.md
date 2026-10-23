# VAICS Sign – Architecture
**Backend** (FastAPI, `CMS-Backend`): `app/main.py` mounts only `auth` (CMS login/users/JWT) and `sign` (`app/routers/sign.py`, prefix `/api/v1/sign`). Models in `app/sign_models.py`. Settings `SignSettings` in `app/config.py`. Tables auto-created at startup + `ensure_columns()` adds new columns to existing sign tables (no Alembic migration yet). PDF stamping: pypdf + reportlab, script font `app/assets/GreatVibes-Regular.ttf` (SIL OFL).
**Frontend** (React/Vite, `CMS-Frontend`): routes `/login`, `/vaics-sign` (dashboard), `/vaics-sign/new` (upload), `/vaics-sign/:id` (prepare on rendered PDF / track / audit), `/vaics-sign/outbox`, public `/sign/:token` (signer portal), `/sign-download/:t`. PDF rendering: `pdfjs-dist` in `pages/sign/PdfPages.jsx`.

## Data model
- `sign_documents`: org, owner (requester), status, original file path + SHA-256, `version_hash` (rolls forward after each signer), completed file + SHA-256, expiry.
- `sign_recipients` (signers, strict `order`): status, token_hash/expiry/revoked, `code_hash` (HMAC-SHA256 with SECRET_KEY), code expiry, attempts, locked, session_hash/expiry (after code), download_hash/expiry, signed_at/IP.
- `sign_fields`: recipient, page, x, y, w, h (fractions of page, origin top-left), reason, signed_at, field_hash.
- `sign_audit_events`: event, actor, IP, UA, doc hash, prev_hash, entry_hash (hash chain).
- `sign_emails`: every generated email (to, kind, subject, body, link, attachment, delivery = smtp_accepted | smtp_failed | dev_outbox; `code` only stored in dev-outbox mode).

## Lifecycle
draft → (Generate) sent → viewed (signer unlocked with code) → partially_signed → completed; or declined / cancelled / expired.
Signer turn: only the lowest-order unsigned signer has a valid link; `by_token` rejects anyone else ("not your turn"). On sign: token + session revoked, field hashes computed, `notify_next` issues link + code to the next signer. After the last signer `finalize()` stamps the original (original never modified), appends certificate, stores result and emails requester + all signers.
Field hash = SHA-256(version_hash | recipient id | email | name | field id | UTC timestamp | reason). Version hash after signer = SHA-256(previous version hash + that signer's field hashes).
