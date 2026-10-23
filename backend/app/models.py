"""VAICS Sign data model. Every tenant-owned table carries org_id and every query is scoped by it."""
from datetime import datetime, timezone
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, Float, Boolean, JSON, UniqueConstraint, Index, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .core.db import Base


def now() -> datetime:
    """Naive UTC (stored as UTC everywhere)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def S(n=255, null=True, **kw):
    return mapped_column(String(n), nullable=null, **kw)


# ---------------- plans & tenants ----------------
class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = S(40, False, unique=True)
    name: Mapped[str] = S(80, False)
    description: Mapped[str] = mapped_column(Text, default="")
    features: Mapped[dict] = mapped_column(JSON, default=dict)  # feature flag -> bool
    limits: Mapped[dict] = mapped_column(JSON, default=dict)  # envelopes_per_month, seats, bulk_max_rows, sms_per_month, api_calls_per_min, storage_mb
    prices: Mapped[dict] = mapped_column(JSON, default=dict)  # {"INR": {"monthly": 0, "annual": 0}, "USD": {...}} per seat
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = S(200, False)
    slug: Mapped[str] = S(80, False, unique=True)
    country: Mapped[str] = S(2, False, default="IN")
    region: Mapped[str] = S(4, False, default="in")  # in | eu | us (data residency)
    status: Mapped[str] = S(20, False, default="trial")  # trial | active | past_due | restricted | suspended | closed
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    billing_cycle: Mapped[str] = S(10, False, default="monthly")
    seats: Mapped[int] = mapped_column(Integer, default=1)
    currency: Mapped[str] = S(3, False, default="INR")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trial_reminded: Mapped[bool] = mapped_column(Boolean, default=False)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    grace_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tax_id: Mapped[str | None] = S(40)
    billing_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_state_code: Mapped[str | None] = S(4)
    po_reference: Mapped[str | None] = S(80)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    branding: Mapped[dict] = mapped_column(JSON, default=dict)
    support_access_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_sandbox: Mapped[bool] = mapped_column(Boolean, default=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    suspended_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    plan: Mapped["Plan"] = relationship(lazy="joined")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=True)  # None = platform staff
    email: Mapped[str] = S(254, False, unique=True)
    full_name: Mapped[str] = S(120, False)
    title: Mapped[str | None] = S(120)
    company: Mapped[str | None] = S(200)
    role: Mapped[str] = S(30, False, default="sender")  # org_admin | billing_admin | sender | template_manager | auditor | viewer | platform_admin
    password_hash: Mapped[str | None] = S(200)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    mfa_secret: Mapped[str | None] = S(64)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_recovery_hashes: Mapped[list] = mapped_column(JSON, default=list)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_history: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[str] = S(8, False, default="en")
    timezone: Mapped[str] = S(40, False, default="Asia/Kolkata")
    notify_prefs: Mapped[dict] = mapped_column(JSON, default=dict)
    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_ip: Mapped[str | None] = S(64)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class UserSession(Base):
    __tablename__ = "user_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # random sid embedded in JWT
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    ip: Mapped[str | None] = S(64)
    user_agent: Mapped[str | None] = S(300)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_passed: Mapped[bool] = mapped_column(Boolean, default=False)


class OneTimeToken(Base):
    """Email verification, password reset, invitation, PowerForm email verification. Only hashes are stored."""
    __tablename__ = "one_time_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = S(20, False)  # verify_email | reset_password | invite | powerform
    token_hash: Mapped[str] = S(64, False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    email: Mapped[str | None] = S(254)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = S(254, False)
    role: Mapped[str] = S(30, False)
    token_id: Mapped[int] = mapped_column(ForeignKey("one_time_tokens.id"))
    invited_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = S(20, False, default="pending")  # pending | accepted | revoked | expired
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class LegalAcceptance(Base):
    __tablename__ = "legal_acceptances"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    document: Mapped[str] = S(20, False)  # tos | privacy | dpa
    version: Mapped[str] = S(20, False)
    ip: Mapped[str | None] = S(64)
    accepted_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = S(120, False)
    member_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # None = shared
    name: Mapped[str] = S(120, False)
    email: Mapped[str] = S(254, False)
    phone: Mapped[str | None] = S(30)
    company: Mapped[str | None] = S(200)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ---------------- templates ----------------
class Template(Base):
    __tablename__ = "templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = S(200, False)
    description: Mapped[str] = mapped_column(Text, default="")
    sharing: Mapped[str] = S(10, False, default="private")  # private | group | org
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    documents: Mapped[list] = mapped_column(JSON, default=list)  # [{name, storage_key, sha256, pages}]
    roles: Mapped[list] = mapped_column(JSON, default=list)  # [{role, order, type, auth, name?, email?, locked}]
    fields: Mapped[list] = mapped_column(JSON, default=list)  # [{role_index, doc_index, type, page, x,y,w,h, ...props}]
    message: Mapped[str] = mapped_column(Text, default="")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    favourite_of: Mapped[list] = mapped_column(JSON, default=list)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class TemplateVersion(Base):
    __tablename__ = "template_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ---------------- envelopes ----------------
class Envelope(Base):
    __tablename__ = "envelopes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    public_id: Mapped[str] = S(40, False, unique=True)  # e.g. VS-7Q2K9M3X
    title: Mapped[str] = S(200, False)
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = S(20, False, default="draft", index=True)  # draft|sent|delivered|partially_signed|completed|declined|voided|expired
    visibility: Mapped[str] = S(10, False, default="private")  # private | group
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    labels: Mapped[list] = mapped_column(JSON, default=list)
    folder: Mapped[str | None] = S(120)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("templates.id"), nullable=True)
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bulk_job_id: Mapped[int | None] = mapped_column(ForeignKey("bulk_jobs.id"), nullable=True, index=True)
    powerform_id: Mapped[int | None] = mapped_column(ForeignKey("powerforms.id"), nullable=True)
    language: Mapped[str] = S(8, False, default="en")
    brand: Mapped[dict] = mapped_column(JSON, default=dict)
    reminder_first_days: Mapped[int] = mapped_column(Integer, default=2)
    reminder_every_days: Mapped[int] = mapped_column(Integer, default=2)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expiry_warned: Mapped[bool] = mapped_column(Boolean, default=False)
    sender_notify: Mapped[dict] = mapped_column(JSON, default=dict)
    version_hash: Mapped[str | None] = S(64)
    completed_key: Mapped[str | None] = S(400)
    completed_sha256: Mapped[str | None] = S(64)
    certificate_key: Mapped[str | None] = S(400)
    sealed: Mapped[str] = S(30, False, default="no")  # no | pades_dev_selfsigned | pades | pades_timestamped
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sandbox: Mapped[bool] = mapped_column(Boolean, default=False)
    search_text: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    documents: Mapped[list["EnvelopeDocument"]] = relationship(order_by="EnvelopeDocument.order", cascade="all, delete-orphan")
    recipients: Mapped[list["Recipient"]] = relationship(order_by="(Recipient.order, Recipient.id)", cascade="all, delete-orphan")
    fields: Mapped[list["Field"]] = relationship(order_by="Field.id", cascade="all, delete-orphan")


class EnvelopeDocument(Base):
    __tablename__ = "envelope_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    envelope_id: Mapped[int] = mapped_column(ForeignKey("envelopes.id"), index=True)
    order: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = S(255, False)
    source_name: Mapped[str] = S(255, False)
    source_type: Mapped[str] = S(100, False, default="application/pdf")
    storage_key: Mapped[str] = S(400, False)
    sha256: Mapped[str] = S(64, False)
    source_sha256: Mapped[str | None] = S(64)  # hash of the uploaded file before conversion
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    pages: Mapped[list] = mapped_column(JSON, default=list)  # [{w,h,rotation}] in PDF points (displayed orientation)
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Recipient(Base):
    __tablename__ = "recipients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    envelope_id: Mapped[int] = mapped_column(ForeignKey("envelopes.id"), index=True)
    role_name: Mapped[str | None] = S(80)  # template role label e.g. "Organization representative"
    type: Mapped[str] = S(20, False, default="signer")  # signer | approver | viewer | cc | in_person | witness | editor
    name: Mapped[str] = S(120, False)
    email: Mapped[str] = S(254, False)
    phone: Mapped[str | None] = S(30)
    order: Mapped[int] = mapped_column(Integer, default=1)
    language: Mapped[str] = S(8, False, default="en")
    private_message: Mapped[str] = mapped_column(Text, default="")
    auth_method: Mapped[str] = S(20, False, default="access_code")  # none | access_code | email_otp | sms_otp
    sender_set_code: Mapped[bool] = mapped_column(Boolean, default=False)
    host_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = S(20, False, default="created")  # created|sent|delivered|authenticated|completed|declined
    token_hash: Mapped[str | None] = S(64, index=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    token_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    code_hash: Mapped[str | None] = S(64)
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    code_attempts: Mapped[int] = mapped_column(Integer, default=0)
    code_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    otp_sends: Mapped[int] = mapped_column(Integer, default=0)
    session_hash: Mapped[str | None] = S(64)
    session_last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    signature_kind: Mapped[str | None] = S(10)  # typed | drawn | uploaded
    signature_style: Mapped[str | None] = S(30)
    signature_image: Mapped[str | None] = mapped_column(Text, nullable=True)  # data URL (drawn/uploaded)
    initials: Mapped[str | None] = S(10)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_reminded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminders_sent: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_ip: Mapped[str | None] = S(64)
    completed_ua: Mapped[str | None] = S(300)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    id_verification: Mapped[dict] = mapped_column(JSON, default=dict)  # in-person host verification
    email_status: Mapped[str | None] = S(20)  # delivered | bounced | complaint
    download_hash: Mapped[str | None] = S(64, index=True)
    download_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    signature_type: Mapped[str] = S(20, False, default="electronic")  # electronic | aadhaar_esign | dsc | qes


FIELD_TYPES = ("signature", "initials", "date_signed", "name", "email", "company", "title", "text", "number", "date",
               "checkbox", "radio", "dropdown", "attachment", "stamp", "formula")


class Field(Base):
    __tablename__ = "fields"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    envelope_id: Mapped[int] = mapped_column(ForeignKey("envelopes.id"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("envelope_documents.id"), index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("recipients.id"), index=True)
    type: Mapped[str] = S(20, False, default="signature")
    page: Mapped[int] = mapped_column(Integer, default=1)
    x: Mapped[float] = mapped_column(Float)  # normalized 0..1 of displayed page, origin top-left
    y: Mapped[float] = mapped_column(Float)
    w: Mapped[float] = mapped_column(Float, default=0.28)
    h: Mapped[float] = mapped_column(Float, default=0.09)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    read_only: Mapped[bool] = mapped_column(Boolean, default=False)
    reason_required: Mapped[bool] = mapped_column(Boolean, default=True)
    label: Mapped[str | None] = S(120)
    tooltip: Mapped[str | None] = S(200)
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[list] = mapped_column(JSON, default=list)
    validation: Mapped[str | None] = S(30)  # email | number | date | regex
    regex: Mapped[str | None] = S(200)
    font_size: Mapped[float] = mapped_column(Float, default=10)
    group_name: Mapped[str | None] = S(60)  # radio group
    condition: Mapped[dict] = mapped_column(JSON, default=dict)  # {"field_id": .., "equals": ..}
    formula: Mapped[str | None] = S(200)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    field_hash: Mapped[str | None] = S(64)


class AuditEvent(Base):
    """Envelope evidence trail. Hash-chained per envelope; never updated or deleted by the application."""
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, index=True)
    envelope_id: Mapped[int] = mapped_column(Integer, index=True)
    event: Mapped[str] = S(40, False)
    actor: Mapped[str] = S(254, False)
    recipient_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip: Mapped[str | None] = S(64)
    user_agent: Mapped[str | None] = S(300)
    location: Mapped[str | None] = S(120)
    detail: Mapped[str] = mapped_column(Text, default="")
    doc_hash: Mapped[str | None] = S(64)
    prev_hash: Mapped[str | None] = S(64)
    entry_hash: Mapped[str] = S(64, False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_email: Mapped[str] = S(254, False)
    action: Mapped[str] = S(60, False)
    target: Mapped[str | None] = S(120)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = S(64)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class EmailLog(Base):
    """Every outgoing email / SMS. With no provider configured this is the DEV OUTBOX (nothing delivered)."""
    __tablename__ = "email_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    envelope_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    channel: Mapped[str] = S(10, False, default="email")  # email | sms
    to: Mapped[str] = S(254, False)
    kind: Mapped[str] = S(40, False)
    subject: Mapped[str] = S(300, False)
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str | None] = S(600)
    secret: Mapped[str | None] = S(20)  # code/OTP kept ONLY in dev-outbox mode
    attachment: Mapped[str | None] = S(255)
    delivery: Mapped[str] = S(20, False)  # dev_outbox | accepted | failed | bounced | complaint
    provider_id: Mapped[str | None] = S(200)
    error: Mapped[str | None] = S(300)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    envelope_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = S(300, False)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ---------------- bulk & powerforms ----------------
class BulkJob(Base):
    __tablename__ = "bulk_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"))
    name: Mapped[str] = S(200, False)
    status: Mapped[str] = S(20, False, default="validated")  # validated | sending | done | failed
    total: Mapped[int] = mapped_column(Integer, default=0)
    valid: Mapped[int] = mapped_column(Integer, default=0)
    sent: Mapped[int] = mapped_column(Integer, default=0)
    rows: Mapped[list] = mapped_column(JSON, default=list)  # [{row, data, errors, envelope_id}]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class PowerForm(Base):
    __tablename__ = "powerforms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"))
    slug: Mapped[str] = S(40, False, unique=True)
    name: Mapped[str] = S(200, False)
    signer_role_index: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uses: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ---------------- billing & usage ----------------
class UsageRecord(Base):
    __tablename__ = "usage_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, index=True)
    metric: Mapped[str] = S(30, False)  # envelopes | sms | api_calls | storage_bytes | aadhaar | dsc | idv
    quantity: Mapped[int] = mapped_column(BigInteger, default=1)
    period: Mapped[str] = S(7, False, index=True)  # YYYY-MM
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Credit(Base):
    __tablename__ = "credits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, index=True)
    metric: Mapped[str] = S(30, False)
    quantity: Mapped[int] = mapped_column(Integer)
    reference: Mapped[str | None] = S(120)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    number: Mapped[str] = S(40, False, unique=True)
    status: Mapped[str] = S(20, False, default="open")  # open | paid | failed | void
    currency: Mapped[str] = S(3, False)
    lines: Mapped[list] = mapped_column(JSON, default=list)
    subtotal: Mapped[int] = mapped_column(Integer, default=0)  # minor units
    tax: Mapped[dict] = mapped_column(JSON, default=dict)  # {"type": "IGST", "rate": 18, "amount": ...}
    total: Mapped[int] = mapped_column(Integer, default=0)
    customer_tax_id: Mapped[str | None] = S(40)
    po_reference: Mapped[str | None] = S(80)
    provider: Mapped[str | None] = S(20)
    provider_ref: Mapped[str | None] = S(120)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Coupon(Base):
    __tablename__ = "coupons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = S(40, False, unique=True)
    percent_off: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ---------------- API & webhooks ----------------
class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))  # acts as this user
    name: Mapped[str] = S(120, False)
    prefix: Mapped[str] = S(16, False, index=True)
    key_hash: Mapped[str] = S(64, False, unique=True)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Webhook(Base):
    __tablename__ = "webhooks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    url: Mapped[str] = S(500, False)
    secret: Mapped[str] = S(80, False)  # used for HMAC signing (shown once)
    events: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhooks.id"), index=True)
    org_id: Mapped[int] = mapped_column(Integer, index=True)
    event: Mapped[str] = S(60, False)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = S(20, False, default="pending")  # pending | delivered | failed | retrying
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = S(300)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("org_id", "key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer)
    key: Mapped[str] = S(120, False)
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ---------------- privacy ----------------
class DataSubjectRequest(Base):
    __tablename__ = "dsr_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, index=True)
    email: Mapped[str] = S(254, False)
    kind: Mapped[str] = S(20, False)  # access | correct | erase
    status: Mapped[str] = S(20, False, default="completed")
    outcome: Mapped[str] = mapped_column(Text, default="")
    requested_by: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class DeletionRecord(Base):
    __tablename__ = "deletion_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, index=True)
    envelope_public_id: Mapped[str | None] = S(40)
    reason: Mapped[str] = S(60, False)  # retention | user_delete | tenant_closure | dsr_erase
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


Index("ix_recipients_email", Recipient.email)
