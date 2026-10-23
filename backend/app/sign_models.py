"""VAICS Sign data models."""
from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, Float, Boolean, inspect, text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
from .models import now


class SignDocument(Base):
    __tablename__ = "sign_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, default=1, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(60), default="General")
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    sequential: Mapped[bool] = mapped_column(Boolean, default=True)
    message: Mapped[str] = mapped_column(Text, default="")
    original_path: Mapped[str] = mapped_column(String(400))
    original_sha256: Mapped[str] = mapped_column(String(64))
    original_name: Mapped[str] = mapped_column(String(255))
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    version_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # rolls forward after each signer
    completed_path: Mapped[str | None] = mapped_column(String(400), nullable=True)
    completed_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class SignRecipient(Base):
    __tablename__ = "sign_recipients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("sign_documents.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="signer")
    order: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|sent|viewed|signed|declined
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    token_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    code_attempts: Mapped[int] = mapped_column(Integer, default=0)
    code_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    session_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    download_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    download_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    signature_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    signature_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    signed_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class SignField(Base):
    __tablename__ = "sign_fields"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("sign_documents.id"), index=True)
    recipient_id: Mapped[int] = mapped_column(Integer, ForeignKey("sign_recipients.id"))
    type: Mapped[str] = mapped_column(String(20), default="signature")
    page: Mapped[int] = mapped_column(Integer, default=1)
    x: Mapped[float] = mapped_column(Float)  # normalized 0..1 from left
    y: Mapped[float] = mapped_column(Float)  # normalized 0..1 from top
    w: Mapped[float] = mapped_column(Float, default=0.3)
    h: Mapped[float] = mapped_column(Float, default=0.1)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    field_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SignAuditEvent(Base):
    __tablename__ = "sign_audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("sign_documents.id"), index=True)
    event: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(200))
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    doc_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class SignEmail(Base):
    """Every outgoing email. When SMTP is not configured this is the DEV outbox (not delivered)."""
    __tablename__ = "sign_emails"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("sign_documents.id"), index=True)
    to: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))  # signing_link|access_code|completed
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    code: Mapped[str | None] = mapped_column(String(10), nullable=True)  # only kept in dev mode (not delivered)
    attachment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery: Mapped[str] = mapped_column(String(20))  # smtp_accepted|dev_outbox|smtp_failed
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


def ensure_columns(engine):
    """Lightweight forward-only column add for existing DBs (no Alembic migration yet)."""
    insp = inspect(engine)
    with engine.begin() as con:
        for t in (SignDocument, SignRecipient, SignField, SignAuditEvent, SignEmail):
            tbl = t.__table__
            if not insp.has_table(tbl.name):
                continue
            have = {c["name"] for c in insp.get_columns(tbl.name)}
            for col in tbl.columns:
                if col.name not in have:
                    con.execute(text(f'ALTER TABLE {tbl.name} ADD COLUMN "{col.name}" {col.type.compile(engine.dialect)}'))
