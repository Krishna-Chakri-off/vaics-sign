# Management demo script (~10 minutes)
Prep: start backend and frontend (SETUP.md), run `python -m app.seed` for a clean demo DB, have a 1–2 page PDF ready. Without SMTP, emails go to the in-app **Email outbox** (DEV EMAIL OUTBOX); say so explicitly — no email is delivered.

1. **Login** at http://localhost:5175 as `manager@vaics.com` / `Demo@123` (the requester). The dashboard shows live counts by status (all from the DB).
2. **New document** → choose PDF, title → Upload. You land on the prepare screen with the PDF rendered page by page.
3. **Signers (strict order)**: Signer 1 = VAICS representative (e.g. "Ravi Kumar", your email), **+ Add signer** → Signer 2 = countersigner (e.g. client). Use ↑/↓ to reorder. The requester is shown as automatic CC.
4. **Place fields**: click Signer 1's card (blue), click on the PDF where they sign (drops a box) or drag to draw one; add a second field on another page to show multiple fields. Select Signer 2 (magenta) and place theirs. Drag boxes to move, corner to resize, × to delete. **Save draft** (drafts are editable).
5. **Generate**. Message: Signer 1 notified. Open **Email outbox**: two separate emails to Signer 1 — the link and the access code. Nothing yet for Signer 2 (order enforcement).
6. Open Signer 1's link in a private/incognito window. **Security demo**: enter a wrong code → "Incorrect access code, N attempts left" (5 wrong = locked; sender can "Revoke & reissue link + code"). Enter the right code → document unlocks.
7. Press **Start** → jumps to the first field. Each field shows the script signature from the signer's name; type a **Reason** (e.g. "Approved on behalf of VAICS"). **Next field** for the rest, tick consent, **Sign & finish**.
8. Back in the outbox (Refresh): Signer 2 now has link + code. Open, unlock, Start, reasons, Sign & finish. The final-signer message appears.
9. Document page shows **Completed**. **Download signed PDF**: stamps at the exact positions with signature, name, reason, IST + UTC time and SHA-256; last page = Certificate of Completion (signers, IPs, field hashes, hash-chained audit trail).
10. Outbox shows **completion emails to 3 parties** (requester + both signers), with download links. Show the audit trail table on the document page and that old signer links now say "Invalid or revoked link".
Optional: Decline (as a signer) or Cancel (as requester) on another document; dashboard counts update.

Real email: set SMTP_* for Amazon SES (ENVIRONMENT_VARIABLES.md), restart backend; outbox then shows "Accepted by SMTP server" (means SES accepted it, not that it was read), codes are no longer displayed and the completed PDF is attached. Not verified with real SES credentials.

Operational: everything above. Dev fallback: email outbox. Not implemented: SMS/OTP to phone, reminders, templates, bulk send, Aadhaar eSign / DSC, drawn signatures (v2 uses name-generated signatures only), touch drag for field placement on mobile (signing on mobile works; preparing is desktop-mouse oriented).
