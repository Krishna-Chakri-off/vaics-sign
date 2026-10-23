# VAICS Sign (v2 – standalone)
VAICS-branded electronic signing app (built from the VAICS CMS codebase; CMS screens removed).

Workflow
1. A logged-in VAICS user (requester) uploads a PDF, adds signers in strict order (Signer 1 = VAICS representative, Signer 2 = countersigner, …) and places one or more signature fields per signer by clicking / dragging directly on the rendered PDF pages (pdf.js). Fields are stored as page + normalized x/y/w/h. The requester is automatically CC.
2. **Generate** emails Signer 1 a signing link and, in a separate email, a 6-digit access code (hash only stored; expiry; 5 attempts then lockout). Signer 2 is not notified yet.
3. Signer portal: enter code → document unlocks → **Start** jumps to the next field → each field shows a script-style signature generated from the signer's name, with a required **Reason** → tick consent → **Sign & finish**.
4. Signer 1 done → Signer 2 automatically gets link + code; same flow.
5. All done → final PDF with stamps at exact positions (signature, name, reason, IST + UTC timestamp, SHA-256) + Certificate of Completion page, emailed to requester and all signers (attachment when SMTP is configured, plus authenticated / tokenised download link).

No SMTP configured → nothing is sent; all emails appear in **Email outbox** (labelled DEV EMAIL OUTBOX, shows links and codes).
