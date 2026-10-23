# Test report – VAICS Sign v2 (22 Oct 2026, build box: Linux, Python 3.13, Node/Vite)
| Command | Result |
|---|---|
| `python -m pytest -q` (CMS-Backend) | **6 passed** |
| `npm run build` (CMS-Frontend) | **Success** |
| Scripted end-to-end run + `pdftoppm` render of the signed PDF | Stamp visually verified (script signature, name, reason, IST + UTC, SHA-256); certificate page rendered |
| Startup against a DB with v1 sign tables | `ensure_columns` added the new columns |

Tests (`tests/test_sign.py`):
1. non-PDF rejected (415), unauthenticated 401.
2. Full two-signer flow: Generate notifies only signer 1; link and code in separate emails; PDF/doc locked without code (401); sign with reasons on 2 fields each; link single-use; signer 2 notified only after signer 1; completed PDF contains Reason/IST/UTC/SHA-256 and certificate; completion emails to exactly requester + 2 signers; signer download link works; required audit events; hash chain valid; dashboard count.
3. Wrong code → 403 ×4, 5th → 423 lockout, correct code still locked; reissue revokes old link; new code works.
4. Order enforcement: signer 2 cannot be reissued/notified before signer 1.
5. Tenant/owner isolation (403), decline, cancel revokes link.
6. Generate requires ≥1 field per signer.
CMS change-management tests were removed with the CMS routers (v2 is VAICS Sign only).

**Not verified**: the UI was not clicked through in a browser (compiled only); click/drag placement and the signer portal therefore untested by hand; real SES/SMTP delivery and attachments (no credentials); Windows execution; mobile layouts; encrypted or unusual PDFs (rotated pages / non-zero CropBox may misplace stamps — mediabox offset is handled, page rotation is not).
