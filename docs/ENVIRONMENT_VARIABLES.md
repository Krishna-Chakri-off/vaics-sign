# Environment variables (backend `.env`) – none strictly required for a local demo
| Var | Purpose | Example / default | Required |
|---|---|---|---|
| SECRET_KEY | JWT signing + access-code HMAC | long random string | Yes in production |
| SMTP_HOST | SMTP server; empty = DEV EMAIL OUTBOX | email-smtp.ap-south-1.amazonaws.com | For real email |
| SMTP_PORT | 587 (STARTTLS) or 465 | 587 | |
| SMTP_USER / SMTP_PASSWORD | SES SMTP credentials (from AWS SES console → SMTP settings → create SMTP credentials) | `<ses-smtp-username>` | For real email |
| SMTP_FROM | Verified SES sender identity | smart.servicedesk@vaics-consulting.com (placeholder; must be verified in SES) | For real email |
| SIGN_SMTP_SSL | true for port 465 implicit TLS | false | |
| SIGN_ORG_NAME / SIGN_PRODUCT_NAME | White-label names (emails, portal, certificate) | VAICS Consulting / VAICS Sign | |
| SIGN_PRIMARY_COLOR / SIGN_ACCENT_COLOR | Email/certificate colours | #0D47A1 / #E6007E | |
| SIGN_LOGO_URL | Signer portal logo | /vaics-logo-full.png | |
| SIGN_STORAGE_DIR | Private PDF storage | ./sign_storage | |
| SIGN_MAX_UPLOAD_MB | Upload limit | 15 | |
| SIGN_LINK_EXPIRY_DAYS | Link / envelope expiry | 7 | |
| SIGN_CODE_LENGTH | Access code digits (6–8) | 6 | |
| SIGN_CODE_MAX_ATTEMPTS | Wrong codes before lockout | 5 | |
| SIGN_CODE_EXPIRY_HOURS | Code validity | 72 | |
| SIGN_SESSION_MINUTES | Unlocked signing session | 30 | |
| SIGN_PUBLIC_BASE_URL | Frontend URL used in emailed links | http://localhost:5175 | Yes when deployed |
Frontend: `VITE_API_URL` (default http://localhost:8000/api/v1). New SES accounts are in sandbox mode: recipients must be verified until production access is granted.
