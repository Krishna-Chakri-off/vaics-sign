# FRS Traceability

> Self-assessed by the build agent from code and tests; not independently audited. FR-201..209 and non-functional requirements are tracked in SECURITY.md / ARCHITECTURE.md.

Requirements marked **Removed** belonged to the original multi-tenant SaaS scope and do not apply to the internal VAICS tool.

Honest status per FRS requirement as of this build. Legend: **Done** (implemented and exercised by tests or the E2E run), **Partial** (core path works, listed gaps), **Interface only** (adapter/API exists, refuses with a clear not-configured error, never reports fake success), **Not implemented**.

Summary (before the SaaS scope was removed): Partial: 48, Done: 97, Not implemented: 54, Interface only: 10 (of 209).

| FR | Requirement | Priority | Release | Status | Notes |
|---|---|---|---|---|---|
| FR-001 | Self-service sign-up | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-002 | Email verification | Must | R1 | Done |  |
| FR-003 | Organization creation | Must | R1 | Done |  |
| FR-004 | Free trial | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-005 | Trial expiry | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-006 | Guided onboarding | Should | R1 | Partial | Sample/first-run hints only; no guided tour |
| FR-007 | Domain claim | Should | R3 | Not implemented |  |
| FR-008 | Invite users | Must | R1 | Done |  |
| FR-009 | Terms and privacy acceptance | Must | R1 | Done |  |
| FR-010 | Plan catalogue | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-011 | Feature entitlements | Must | R1 | Done |  |
| FR-012 | Online purchase | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-013 | Payment gateways | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-014 | Tax invoices | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-015 | Seats | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-016 | Usage limits and metering | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-017 | Overage and top-ups | Should | R2 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-018 | Failed payment handling | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-019 | Enterprise contracts | Should | R2 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-020 | Billing history | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-021 | Coupons and partner pricing | Could | R3 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-022 | Org Admin console | Must | R1 | Done |  |
| FR-023 | User lifecycle | Must | R1 | Done |  |
| FR-024 | Groups and teams | Must | R2 | Done | Groups + group sharing of templates |
| FR-025 | Custom roles | Should | R3 | Not implemented |  |
| FR-026 | Multiple accounts per organization | Should | R4 | Not implemented |  |
| FR-027 | Organization settings | Must | R1 | Done |  |
| FR-028 | Admin audit log | Must | R1 | Done |  |
| FR-029 | Platform Admin console | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-030 | Tenant suspension and closure | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-031 | Password sign-in | Must | R1 | Done |  |
| FR-032 | Social sign-in | Should | R1 | Not implemented | Returns 501 |
| FR-033 | Password policy | Must | R1 | Partial | Length/complexity/history; HIBP check optional (off by default); expiry basic |
| FR-034 | Password reset | Must | R1 | Done |  |
| FR-035 | Multi-factor authentication | Must | R1 | Partial | TOTP done + enforce; passkeys and SMS MFA not done |
| FR-036 | Single sign-on | Must | R3 | Not implemented |  |
| FR-037 | SCIM provisioning | Should | R3 | Not implemented |  |
| FR-038 | Session management | Must | R1 | Done |  |
| FR-039 | Login protection | Must | R1 | Done |  |
| FR-040 | IP allow-lists | Could | R3 | Not implemented |  |
| FR-041 | Organization branding | Must | R1 | Done |  |
| FR-042 | Multiple brands | Should | R2 | Not implemented |  |
| FR-043 | Custom email sender | Must | R2 | Not implemented |  |
| FR-044 | Custom signing domain | Should | R3 | Not implemented |  |
| FR-045 | Editable email templates | Must | R2 | Partial | Fixed templates with branding; per-language editor not done |
| FR-046 | Custom legal text | Must | R1 | Partial | Custom disclosure text in settings |
| FR-047 | Full white-label for partners | Should | R4 | Not implemented |  |
| FR-048 | Supported formats | Must | R1 | Partial | PDF + images; Office via LibreOffice only if installed (optional in Docker) |
| FR-049 | Upload sources | Must | R1 | Partial | Computer/drag-drop/templates; cloud pickers not done |
| FR-050 | File limits | Must | R1 | Done |  |
| FR-051 | Validation and malware scan | Must | R1 | Partial | Type/integrity checks; ClamAV only if CLAMD_HOST set |
| FR-052 | Original fingerprint | Must | R1 | Done |  |
| FR-053 | Multiple documents per envelope | Must | R1 | Done |  |
| FR-054 | Page handling | Must | R1 | Partial | Rotation/cropbox handled via page matrix; tested on simple cases |
| FR-055 | Drafts | Must | R1 | Done |  |
| FR-056 | Envelope correction | Should | R2 | Done |  |
| FR-057 | Folders and labels | Should | R2 | Partial | Folder and labels fields + filters; no folder management UI beyond basic |
| FR-058 | Document visibility | Must | R1 | Partial | Private/shared visibility; admin view-all |
| FR-059 | Create template | Must | R2 | Done |  |
| FR-060 | Template roles | Must | R2 | Done |  |
| FR-061 | Template sharing | Must | R2 | Partial | Private/group/org sharing; fine-grained edit/use permissions limited |
| FR-062 | Template versioning | Should | R2 | Done |  |
| FR-063 | Pre-filled data | Must | R2 | Done |  |
| FR-064 | Template library | Should | R2 | Done | Search/filter/favourite |
| FR-065 | Combine templates | Could | R3 | Not implemented |  |
| FR-066 | Visual placement | Must | R1 | Done |  |
| FR-067 | Multiple fields per signer | Must | R1 | Done |  |
| FR-068 | Recipient colour coding | Must | R1 | Done |  |
| FR-069 | Field types | Must | R1 | Partial | Most types; attachment-field file upload not implemented |
| FR-070 | Field properties | Must | R1 | Partial | Required/read-only/default/tooltip; font options limited |
| FR-071 | Conditional fields | Should | R2 | Done | Show/hide by field_id condition |
| FR-072 | Calculated fields | Could | R3 | Not implemented |  |
| FR-073 | Text tags | Should | R2 | Not implemented |  |
| FR-074 | Auto-detect fields | Could | R3 | Not implemented |  |
| FR-075 | Validation before send | Must | R1 | Done |  |
| FR-076 | Touch support | Must | R2 | Done |  |
| FR-077 | Add recipients | Must | R1 | Done |  |
| FR-078 | Signing order | Must | R1 | Done |  |
| FR-079 | Sequential routing | Must | R1 | Done |  |
| FR-080 | Parallel and mixed routing | Must | R1 | Done |  |
| FR-081 | Recipient roles | Must | R2 | Done |  |
| FR-082 | Requester copy | Must | R1 | Done |  |
| FR-083 | Signing groups | Should | R2 | Not implemented |  |
| FR-084 | Conditional routing | Should | R3 | Not implemented |  |
| FR-085 | Reassignment | Should | R2 | Not implemented |  |
| FR-086 | Contacts | Should | R1 | Partial | Contacts model/API; minimal UI |
| FR-087 | Private message | Must | R1 | Done |  |
| FR-088 | Void and resend | Must | R1 | Done |  |
| FR-089 | Signing invitation | Must | R1 | Done |  |
| FR-090 | Separate access code delivery | Must | R1 | Done |  |
| FR-091 | Next signer notification | Must | R1 | Done |  |
| FR-092 | Automatic reminders | Must | R1 | Done |  |
| FR-093 | Expiry | Must | R1 | Done |  |
| FR-094 | Sender notifications | Must | R1 | Partial | Sender notification events; per-envelope preference toggles basic |
| FR-095 | Completion notification | Must | R1 | Done |  |
| FR-096 | Delivery tracking | Must | R1 | Partial | Email log/outbox states; real bounce/complaint webhooks not wired (SES not connected). Never claims delivery |
| FR-097 | SMS and WhatsApp | Should | R2 | Partial | SMS via Twilio interface (dev outbox by default); WhatsApp not done |
| FR-098 | In-app and push notifications | Should | R2 | Partial | In-app notifications; no push |
| FR-099 | Notification preferences | Should | R1 | Partial | Language preference; per-type preferences limited |
| FR-100 | Secure signing link | Must | R1 | Done |  |
| FR-101 | Access code | Must | R1 | Done |  |
| FR-102 | Email OTP | Must | R1 | Done |  |
| FR-103 | SMS OTP | Must | R2 | Partial | SMS OTP implemented; real SMS only if Twilio configured |
| FR-104 | Attempt limits | Must | R1 | Done |  |
| FR-105 | Signing session | Must | R1 | Done |  |
| FR-106 | Knowledge-based authentication | Could | R3 | Interface only | Provider interface returns not-configured; no fake success |
| FR-107 | Government ID verification | Should | R3 | Interface only | Provider interface returns not-configured; no fake success |
| FR-108 | Aadhaar and DigiLocker verification | Must | R3 | Interface only | Provider interface returns not-configured; no fake success |
| FR-109 | Authentication per recipient | Must | R1 | Done |  |
| FR-110 | Signer authentication for re-access | Must | R1 | Done |  |
| FR-111 | Branded signing page | Must | R1 | Done |  |
| FR-112 | Consent to electronic business | Must | R1 | Done |  |
| FR-113 | Guided signing | Must | R1 | Done |  |
| FR-114 | Automatic signature from name | Must | R1 | Done |  |
| FR-115 | Drawn and uploaded signatures | Must | R1 | Done |  |
| FR-116 | Reason for signing | Must | R1 | Done |  |
| FR-117 | Signature stamp | Must | R1 | Done |  |
| FR-118 | Fill fields | Must | R1 | Partial | Text/checkbox/dropdown/date; attachment upload missing |
| FR-119 | Earlier signatures visible | Must | R1 | Done |  |
| FR-120 | Decline | Must | R1 | Done |  |
| FR-121 | Finish later | Should | R1 | Done |  |
| FR-122 | Review and download | Must | R1 | Done |  |
| FR-123 | Comments | Could | R3 | Not implemented |  |
| FR-124 | Signer language | Must | R2 | Partial | English + Hindi UI strings; PDF Devanagari shaping not supported |
| FR-125 | Responsive signing | Must | R1 | Done |  |
| FR-126 | Electronic signature | Must | R1 | Done |  |
| FR-127 | Organization seal on completed documents | Must | R1 | Partial | PAdES seal via pyHanko; dev self-signed cert unless SEAL_CERT_P12_PATH set; TSA optional |
| FR-128 | Aadhaar eSign | Must | R3 | Interface only | Trust-provider interface only; returns not-configured, never fake success |
| FR-129 | DSC signing | Must | R3 | Interface only | Trust-provider interface only; returns not-configured, never fake success |
| FR-130 | Cloud PKI signatures | Should | R3 | Interface only | Trust-provider interface only; returns not-configured, never fake success |
| FR-131 | eIDAS advanced and qualified signatures | Must | R3 | Interface only | Trust-provider interface only; returns not-configured, never fake success |
| FR-132 | Electronic seals for organizations | Should | R4 | Interface only | Trust-provider interface only; returns not-configured, never fake success |
| FR-133 | Signature type policy | Must | R3 | Partial | Allowed signature kinds in org settings |
| FR-134 | Signature validation | Must | R2 | Partial | Public verify by ID and by upload (pyHanko validation); trust shows self-signed in dev |
| FR-135 | In-person signer role | Must | R2 | Done |  |
| FR-136 | Host verification | Must | R2 | Partial | Host ID type/number recorded |
| FR-137 | Kiosk mode | Should | R2 | Partial | In-person flow hides other envelopes; no hardened kiosk lock |
| FR-138 | Offline signing | Could | R4 | Not implemented |  |
| FR-139 | PowerForm creation | Must | R2 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-140 | Signer details capture | Must | R2 | Removed | Not applicable: PowerForms removed (internal VAICS tool) |
| FR-141 | Embedding | Should | R2 | Removed | Not applicable: PowerForms removed (internal VAICS tool) |
| FR-142 | Usage limits and expiry | Must | R2 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-143 | Web forms | Could | R3 | Not implemented |  |
| FR-144 | Payment fields | Must | R3 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-145 | Payment gateways for customers | Must | R3 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-146 | Pay at signing | Must | R3 | Not implemented |  |
| FR-147 | Payment receipts | Must | R3 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-148 | Bulk send from list | Must | R2 | Done |  |
| FR-149 | List validation | Must | R2 | Done |  |
| FR-150 | Bulk job tracking | Must | R2 | Done |  |
| FR-151 | Bulk actions | Should | R2 | Done |  |
| FR-152 | Bulk limits | Must | R2 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-153 | Finalization | Must | R1 | Done |  |
| FR-154 | Hash chain of versions | Must | R1 | Done |  |
| FR-155 | Certificate of Completion | Must | R1 | Done |  |
| FR-156 | Delivery to all parties | Must | R1 | Done |  |
| FR-157 | Download options | Must | R1 | Partial | Combined PDF + certificate + evidence zip; separate-doc option limited |
| FR-158 | Completed-document storage | Must | R1 | Partial | S3 Object Lock days configurable; local storage is not WORM |
| FR-159 | Automatic export | Should | R2 | Not implemented |  |
| FR-160 | Event capture | Must | R1 | Done |  |
| FR-161 | Event data | Must | R1 | Done |  |
| FR-162 | Tamper evidence | Must | R1 | Partial | Hash-chained events; WORM depends on S3 Object Lock |
| FR-163 | Audit view and export | Must | R1 | Done |  |
| FR-164 | Evidence package | Must | R2 | Done |  |
| FR-165 | Organization activity reports | Must | R2 | Done |  |
| FR-166 | Home dashboard | Must | R1 | Done |  |
| FR-167 | Envelope list | Must | R1 | Done |  |
| FR-168 | Search | Must | R1 | Done |  |
| FR-169 | Standard reports | Must | R2 | Partial | Volume/turnaround/completion/decline reports + CSV |
| FR-170 | Custom reports and export | Should | R3 | Partial | CSV/XLSX export; no custom builder or scheduling |
| FR-171 | Usage dashboard | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-172 | Public REST API | Must | R2 | Done |  |
| FR-173 | API authentication | Must | R2 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-174 | Webhooks | Must | R2 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-175 | Embedded sending and signing | Must | R2 | Not implemented |  |
| FR-176 | SDKs | Should | R3 | Not implemented |  |
| FR-177 | Developer sandbox | Must | R2 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-178 | Rate limits | Must | R2 | Partial | Per-process in-memory limiter; not per-plan, not shared across workers |
| FR-179 | Idempotency | Should | R2 | Done | Idempotency-Key on create |
| FR-180 | Google Drive | Must | R2 | Not implemented |  |
| FR-181 | Microsoft OneDrive and SharePoint | Must | R2 | Not implemented |  |
| FR-182 | Dropbox and Box | Could | R3 | Not implemented |  |
| FR-183 | Salesforce | Must | R3 | Not implemented |  |
| FR-184 | Slack | Should | R2 | Not implemented |  |
| FR-185 | Microsoft Teams | Should | R2 | Not implemented |  |
| FR-186 | Zapier | Must | R2 | Not implemented |  |
| FR-187 | Microsoft 365 and Google Workspace add-ins | Should | R3 | Not implemented |  |
| FR-188 | Other CRM and HR systems | Could | R4 | Not implemented |  |
| FR-189 | iOS and Android apps | Must | R3 | Not implemented |  |
| FR-190 | Scan to send | Should | R3 | Not implemented |  |
| FR-191 | Biometric unlock | Should | R3 | Not implemented |  |
| FR-192 | Mobile device security | Must | R3 | Not implemented |  |
| FR-193 | User interface languages | Must | R2 | Partial | English + Hindi |
| FR-194 | Right-to-left support | Should | R3 | Not implemented |  |
| FR-195 | Regional formats | Must | R1 | Partial | IST/tz-aware timestamps; locale number formats limited |
| FR-196 | Translated notifications | Must | R2 | Not implemented |  |
| FR-197 | Unicode documents | Must | R1 | Partial | Unicode stored; Indic shaping in stamped PDFs not supported |
| FR-198 | Regional data centres | Must | R1 | Not implemented |  |
| FR-199 | Region selection | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
| FR-200 | Region migration | Should | R4 | Not implemented |  |
| FR-201 | Sub-processor transparency | Must | R1 | Not implemented |  |
| FR-202 | Retention policies | Must | R1 | Not implemented |  |
| FR-203 | Automatic purge | Must | R1 | Not implemented |  |
| FR-204 | Legal hold | Must | R2 | Not implemented |  |
| FR-205 | User deletion of envelopes | Must | R1 | Not implemented |  |
| FR-206 | Data-subject requests | Must | R1 | Not implemented |  |
| FR-207 | Privacy notice to recipients | Must | R1 | Not implemented |  |
| FR-208 | Organization data export | Must | R2 | Not implemented |  |
| FR-209 | Tenant closure | Must | R1 | Removed | Not applicable: internal single-organisation VAICS tool (no SaaS plans, billing, tenants or public API) |
