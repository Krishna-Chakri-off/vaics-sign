# Demo guide
1. Seed: `DEMO_PASSWORD=<pw> python -m app.seed --demo`, then start the backend and frontend.
2. Sign in as `krishna@example.com` (Org Admin, VAICS Consulting).
3. **Envelopes → New**: upload a PDF. Add recipient 1 (VAICS representative, order 1) and recipient 2 (countersigner, order 2), and turn on access code + reason required.
4. Prepare: pick a recipient and click or tap on the page to place signature, date and text fields. Fields are colour-coded per recipient. Click **Send**.
5. **Outbox** (dev): each signer gets two emails, one with the link and one with the access code. Open Signer 1's link, enter the code, accept consent, click Start, adopt a signature (type, draw or upload), enter a reason, then Finish.
6. Signer 2 is only invited after that. Repeat the steps.
7. Completion: the sealed PDF and certificate are emailed (outbox) to all parties. Stamps show the reason, IST and UTC time, and the SHA-256 hash. Check it on **/verify** with the envelope ID or by uploading the PDF.
8. Also try: templates and bulk send (CSV/XLSX), PowerForms (public link), void/decline/correct, in-person signing, Admin (users, groups, branding, API keys, webhooks, audit export), Billing (plans and GST invoice PDF; checkout returns "not configured"), Reports, and Platform console (sign in as platform@example.com).
