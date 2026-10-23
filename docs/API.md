# API

Versioned REST API under `/api/v1`. Interactive docs: `/api/docs`. OpenAPI JSON: `/api/v1/openapi.json`. Health: `/api/health`.

**Auth:** user JWT `Authorization: Bearer <token>` (from `POST /api/v1/auth/login`), or an org API key `Authorization: Bearer vsk_...` with scopes (envelopes:read, envelopes:write, templates:read, ...). Responses carry `X-RateLimit-*` headers. Create endpoints accept `Idempotency-Key`.

**Webhooks:** POST JSON events (envelope.sent, recipient.completed, envelope.completed, envelope.declined, envelope.voided, ...). Header `X-VAICS-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, "t.body")>`. Failed deliveries are retried with back-off and are visible at `GET /api/v1/org/webhooks/deliveries`.

**Errors:** JSON `{"detail": ...}`. 401/403 for auth or permission, 404 also for other tenants' objects, 402 for plan limits, 409 for state conflicts, 410 for gone/purged, 429 for rate limits, 501/503 for unimplemented or unconfigured providers.

## Endpoints

```
POST /api/v1/auth/signup
POST /api/v1/auth/verify-email/{token}
POST /api/v1/auth/resend-verification
POST /api/v1/auth/login
GET PATCH /api/v1/auth/me
POST /api/v1/auth/logout
GET /api/v1/auth/sessions
DELETE /api/v1/auth/sessions/{prefix}
POST /api/v1/auth/password/forgot
POST /api/v1/auth/password/reset
POST /api/v1/auth/password/change
POST /api/v1/auth/mfa/setup
POST /api/v1/auth/mfa/enable
POST /api/v1/auth/mfa/disable
POST /api/v1/auth/mfa/enrol-setup
POST /api/v1/auth/mfa/enrol-enable
GET /api/v1/auth/invitations/{token}
POST /api/v1/auth/invitations/accept
GET /api/v1/auth/social/{provider}
POST GET /api/v1/envelopes
GET /api/v1/envelopes/dashboard
GET PUT DELETE /api/v1/envelopes/{env_id}
POST /api/v1/envelopes/{env_id}/documents
DELETE /api/v1/envelopes/{env_id}/documents/{doc_id}
POST /api/v1/envelopes/{env_id}/documents/reorder
GET /api/v1/envelopes/{env_id}/documents/{doc_id}/file
POST /api/v1/envelopes/{env_id}/send
POST /api/v1/envelopes/{env_id}/void
POST /api/v1/envelopes/{env_id}/correct
POST /api/v1/envelopes/{env_id}/recipients/{rid}/reissue
POST /api/v1/envelopes/{env_id}/remind
POST /api/v1/envelopes/{env_id}/extend
POST /api/v1/envelopes/{env_id}/duplicate
POST /api/v1/envelopes/{env_id}/legal-hold
GET /api/v1/envelopes/{env_id}/completed
GET /api/v1/envelopes/{env_id}/certificate
GET /api/v1/envelopes/{env_id}/audit
GET /api/v1/envelopes/{env_id}/evidence
POST /api/v1/envelopes/{env_id}/recipients/{rid}/in-person
GET /api/v1/public/s/{tok}
POST /api/v1/public/s/{tok}/unlock
POST /api/v1/public/s/{tok}/otp
POST /api/v1/public/s/{tok}/open
GET /api/v1/public/s/{tok}/envelope
GET /api/v1/public/s/{tok}/documents/{doc_id}
POST /api/v1/public/s/{tok}/save
POST /api/v1/public/s/{tok}/finish
POST /api/v1/public/s/{tok}/decline
GET /api/v1/public/completed/{dtok}
POST /api/v1/public/completed/{dtok}/otp
POST /api/v1/public/completed/{dtok}/download
GET /api/v1/org/users
GET POST /api/v1/org/invitations
POST /api/v1/org/invitations/{inv_id}/resend
DELETE /api/v1/org/invitations/{inv_id}
PATCH DELETE /api/v1/org/users/{uid}
POST /api/v1/org/users/{uid}/transfer
GET POST /api/v1/org/groups
PUT DELETE /api/v1/org/groups/{gid}
GET PUT /api/v1/org/settings
PUT /api/v1/org/branding
POST /api/v1/org/branding/logo
GET POST /api/v1/org/api-keys
DELETE /api/v1/org/api-keys/{kid}
GET POST /api/v1/org/webhooks
DELETE /api/v1/org/webhooks/{wid}
GET /api/v1/org/webhooks/deliveries
GET /api/v1/org/audit-log
GET POST /api/v1/org/contacts
DELETE /api/v1/org/contacts/{cid}
GET /api/v1/org/outbox
GET /api/v1/org/notifications
POST /api/v1/org/notifications/read-all
GET /api/v1/org/usage
POST /api/v1/org/support-access
GET /api/v1/billing/plans
GET /api/v1/billing/subscription
POST /api/v1/billing/checkout
POST /api/v1/billing/seats
POST /api/v1/billing/credits
POST /api/v1/billing/cancel
GET /api/v1/billing/invoices
GET /api/v1/billing/invoices/{iid}/pdf
GET /api/v1/billing/usage-statement
GET /api/v1/platform/tenants
POST /api/v1/platform/tenants/{oid}/status
POST /api/v1/platform/tenants/{oid}/plan
GET /api/v1/platform/tenants/{oid}/envelopes
GET POST /api/v1/platform/plans
PUT /api/v1/platform/plans/{code}
POST /api/v1/platform/coupons
GET /api/v1/platform/health
GET /api/v1/platform/audit-log
GET /api/v1/platform/subprocessors
GET POST /api/v1/templates
PUT /api/v1/templates/{tid}
GET /api/v1/templates/{tid}/versions
POST /api/v1/templates/{tid}/favourite
POST /api/v1/templates/use
GET POST /api/v1/bulk
POST /api/v1/bulk/{jid}/send
GET /api/v1/bulk/{jid}
GET /api/v1/bulk/{jid}/report.csv
POST /api/v1/envelopes-bulk-action
GET POST /api/v1/powerforms
PATCH /api/v1/powerforms/{fid}
GET /api/v1/public/pf/{slug}
POST /api/v1/public/pf/{slug}/start
POST /api/v1/public/pf/{slug}/verify
GET /api/v1/reports/summary
GET /api/v1/reports/summary.csv
POST /api/v1/public/verify
GET /api/v1/public/verify/{public_id}
GET POST /api/v1/privacy/dsr
GET /api/v1/privacy/deletions
GET /api/v1/privacy/export
GET /api/health
```
