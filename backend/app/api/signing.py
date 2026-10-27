"""Public recipient endpoints (no account). Token = recipient & turn scoped link; session = after authentication."""
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..core.security import sha256_hex
from ..models import Organization, User, Recipient, Envelope, now
from ..services import workflow as wf, audit, notify
from ..services.storage import storage

router = APIRouter(prefix="/public", tags=["signing (public)"])

DEFAULT_CONSENT = ("I agree to use electronic records and signatures for this envelope. I understand that my electronic signature is legally binding "
                   "to the same extent as a handwritten signature where the law allows, that I may request a paper copy from the sender, and that I may "
                   "withdraw this consent before signing by declining.")
DEFAULT_PRIVACY = ("{org} uses {product} to collect your name, email, IP address, device details, signature and the information you enter, "
                   "to complete this agreement and keep evidence of it. Data is stored in the {region} region for the period set by {org}'s retention policy. "
                   "You can request access, correction or erasure of your personal data from {org}.")
REGION_LABEL = {"in": "India", "eu": "European Union", "us": "United States"}


def _ctx(db, tok):
    env, r = wf.recipient_by_token(db, tok)
    return db.get(Organization, env.org_id), env, r


@router.get("/s/{tok}")
def info(tok: str, request: Request, db: Session = Depends(get_db)):
    org, env, r = _ctx(db, tok)
    s = wf.org_settings(org); brand = notify.brand_of(org, env)
    if r.status == "sent":
        r.status = "delivered"
        audit.record(db, env, "opened", r.email, request, "signing link opened", r)
        db.commit()
    owner = db.get(User, env.owner_id)
    return {"envelope_id": env.public_id, "title": env.title, "sender": owner.full_name, "sender_email": owner.email,
            "recipient": {"name": r.name, "email": r.email, "type": r.type, "order": r.order, "auth_method": r.auth_method, "language": r.language,
                          "locked": r.code_locked, "signature_type": r.signature_type},
            "branding": brand, "consent_text": s.get("consent_text") or DEFAULT_CONSENT,
            "privacy_text": s.get("privacy_text") or DEFAULT_PRIVACY.format(org=org.name, product=brand["product_name"], region=REGION_LABEL.get(org.region, org.region)),
            "allowed_signature_kinds": s["allowed_signature_kinds"], "is_sandbox": env.is_sandbox}


class CodeIn(BaseModel):
    code: str


@router.post("/s/{tok}/unlock")
def unlock(tok: str, body: CodeIn, request: Request, db: Session = Depends(get_db)):
    org, env, r = _ctx(db, tok)
    sess = wf.verify_code(db, org, env, r, body.code, request); db.commit()
    return {"session": sess}


@router.post("/s/{tok}/otp")
def otp(tok: str, request: Request, db: Session = Depends(get_db)):
    org, env, r = _ctx(db, tok)
    wf.send_otp(db, org, env, r, request); db.commit()
    return {"sent": True, "channel": "sms" if r.auth_method == "sms_otp" else "email", "mode": "provider" if (notify.sms_configured() if r.auth_method == "sms_otp" else notify.smtp_configured()) else "dev_outbox"}


@router.post("/s/{tok}/open")
def open_without_code(tok: str, request: Request, db: Session = Depends(get_db)):
    org, env, r = _ctx(db, tok)
    if r.auth_method != "none": raise HTTPException(403, "Authentication required")
    sess = wf.open_session(db, env, r, request, "email link"); db.commit()
    return {"session": sess}


def _sess(db, tok, sess):
    env, r = wf.session_recipient(db, tok, sess)
    return db.get(Organization, env.org_id), env, r


@router.get("/s/{tok}/envelope")
def envelope(tok: str, request: Request, x_signer_session: str | None = Header(None), db: Session = Depends(get_db)):
    org, env, r = _sess(db, tok, x_signer_session)
    from ..models import AuditEvent
    last = db.query(AuditEvent).filter_by(envelope_id=env.id, recipient_id=r.id).order_by(AuditEvent.id.desc()).first()
    if not last or last.event not in ("viewed", "progress_saved"):
        audit.record(db, env, "viewed", r.email, request, "document viewed", r)
    rmap = {x.id: x for x in env.recipients}
    mine = [f for f in env.fields if f.recipient_id == r.id]
    others = [f for f in env.fields if f.recipient_id != r.id and f.signed_at]
    db.commit()
    def fo(f, own):
        d = {k: getattr(f, k) for k in ("id", "document_id", "type", "page", "x", "y", "w", "h", "required", "read_only", "reason_required", "label", "tooltip",
                                         "default_value", "options", "validation", "font_size", "group_name", "condition", "formula", "value", "reason")}
        if not own:
            o = rmap[f.recipient_id]
            d.update({"by": o.name, "signed_at": f.signed_at, "signature_kind": o.signature_kind, "signature_style": o.signature_style,
                      "signature_image": o.signature_image if f.type in ("signature", "initials") else None, "field_hash": f.field_hash})
        return d
    return {"title": env.title, "message": env.message, "private_message": r.private_message, "envelope_id": env.public_id,
            "documents": [{"id": d.id, "name": d.name, "pages": d.pages} for d in env.documents],
            "recipient": {"name": r.name, "email": r.email, "type": r.type, "initials": "".join(p[0] for p in r.name.split() if p).upper()},
            "fields": [fo(f, True) for f in mine], "completed_fields": [fo(f, False) for f in others]}


@router.get("/s/{tok}/documents/{doc_id}")
def document(tok: str, doc_id: int, x_signer_session: str | None = Header(None), db: Session = Depends(get_db)):
    org, env, r = _sess(db, tok, x_signer_session)
    d = next((x for x in env.documents if x.id == doc_id), None)
    if not d: raise HTTPException(404, "Document not found")
    db.commit()
    return Response(wf.doc_bytes(org, d), media_type="application/pdf", headers={"Cache-Control": "no-store", "Content-Disposition": f'inline; filename="{d.name}"'})


def _img_mime(data: bytes) -> str:
    return "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"


@router.get("/s/{tok}/company-stamp")
def company_stamp_preview(tok: str, x_signer_session: str | None = Header(None), db: Session = Depends(get_db)):
    """Preview of the official stamp for a signer who owns a Company stamp field (read-only; the server still applies it on finish)."""
    from ..services import companystamp
    org, env, r = _sess(db, tok, x_signer_session)
    if not any(f.type == "stamp" and f.recipient_id == r.id for f in env.fields): raise HTTPException(403, "No company stamp field is assigned to you")
    if not companystamp.is_internal(db, org, r): raise HTTPException(403, "Only an internal VAICS signer can apply the company stamp")
    cur = companystamp.current_image(org)
    if not cur: raise HTTPException(404, "No official company stamp is configured. Ask your VAICS admin to upload it in Settings.")
    return Response(cur[1], media_type=_img_mime(cur[1]), headers={"Cache-Control": "no-store", "X-Stamp-Sha256": cur[0]})


@router.get("/s/{tok}/company-stamp/applied/{field_id}")
def company_stamp_applied(tok: str, field_id: int, x_signer_session: str | None = Header(None), db: Session = Depends(get_db)):
    """The stamp image already applied on a completed field of this envelope (shown to later signers)."""
    from ..services import companystamp
    org, env, r = _sess(db, tok, x_signer_session)
    f = next((x for x in env.fields if x.id == field_id and x.type == "stamp" and x.signed_at), None)
    if not f or not str(f.value or "").startswith("sha256:"): raise HTTPException(404, "Stamp not found")
    data = companystamp.load_applied(org, env.id, f.value.split(":", 1)[1])
    return Response(data, media_type=_img_mime(data), headers={"Cache-Control": "no-store"})


class SaveIn(BaseModel):
    values: dict[int, str] = {}
    reasons: dict[int, str] = {}


@router.post("/s/{tok}/save")
def save_progress(tok: str, body: SaveIn, request: Request, x_signer_session: str | None = Header(None), db: Session = Depends(get_db)):
    """Finish later (FR-121): keep entered values; signatures are only applied on finish."""
    org, env, r = _sess(db, tok, x_signer_session)
    mine = {f.id: f for f in env.fields if f.recipient_id == r.id}
    for k, v in body.values.items():
        if k in mine and mine[k].type not in ("signature", "initials", "date_signed", "name", "email", "stamp"): mine[k].value = v
    for k, v in body.reasons.items():
        if k in mine and mine[k].type == "signature": mine[k].reason = v[:200]
    audit.record(db, env, "progress_saved", r.email, request, f"{len(body.values)} value(s)", r)
    db.commit()
    return {"saved": True}


class FinishIn(BaseModel):
    consent: bool
    intent: bool = False  # signer affirmed the signature-meaning statement
    signature_meaning: str | None = None
    signature: dict = {}
    values: dict[int, str] = {}
    reasons: dict[int, str] = {}


@router.post("/s/{tok}/finish")
def finish(tok: str, body: FinishIn, request: Request, x_signer_session: str | None = Header(None), db: Session = Depends(get_db)):
    org, env, r = _sess(db, tok, x_signer_session)
    actor = r.id_verification.get("host") and f"{r.email} (hosted by {r.id_verification['host']})" if r.type == "in_person" else None
    wf.complete_recipient(db, org, env, r, body.model_dump(), request, actor)
    db.commit()
    return {"status": env.status, "envelope_status": env.status, "completed": env.status == "completed", "kiosk_return": r.type == "in_person"}


class DeclineIn(BaseModel):
    reason: str


@router.post("/s/{tok}/decline")
def decline(tok: str, body: DeclineIn, request: Request, x_signer_session: str | None = Header(None), db: Session = Depends(get_db)):
    org, env, r = _sess(db, tok, x_signer_session)
    wf.decline(db, org, env, r, body.reason, request); db.commit()
    return {"status": env.status}


# ---------- completed document re-access (FR-110: fresh authentication) ----------
def _dl(db, dtok):
    r = db.query(Recipient).filter_by(download_hash=sha256_hex(dtok)).first()
    if not r or not r.download_expires_at or r.download_expires_at < now():
        raise HTTPException(404, "This download link is invalid or has expired")
    env = db.get(Envelope, r.envelope_id)
    if env.status != "completed" or env.purged_at: raise HTTPException(410, "Document no longer available")
    return db.get(Organization, env.org_id), env, r


@router.get("/completed/{dtok}")
def completed_info(dtok: str, db: Session = Depends(get_db)):
    org, env, r = _dl(db, dtok)
    return {"title": env.title, "envelope_id": env.public_id, "recipient": r.name, "email_hint": r.email[:2] + "***@" + r.email.split("@")[1], "branding": notify.brand_of(org, env)}


@router.post("/completed/{dtok}/otp")
def completed_otp(dtok: str, request: Request, db: Session = Depends(get_db)):
    from ..core.security import numeric_code, keyed_hash
    from datetime import timedelta
    from ..core.config import settings
    org, env, r = _dl(db, dtok)
    if r.otp_sends >= 10: raise HTTPException(429, "Too many codes requested")
    code = numeric_code(6)
    r.code_hash, r.code_expires_at, r.code_attempts, r.otp_sends = keyed_hash(f"dl:{r.id}", code), now() + timedelta(minutes=settings.OTP_MINUTES), 0, r.otp_sends + 1
    notify.send_email(db, org=org, to=r.email, kind="otp", envelope=env, code=code, subject="Your code to download the completed document",
                      body=f"Use this code to download \"{env.title}\". Valid {settings.OTP_MINUTES} minutes.")
    audit.record(db, env, "otp_sent", "system", request, "re-access to completed document", r)
    db.commit()
    return {"sent": True}


@router.post("/completed/{dtok}/download")
def completed_download(dtok: str, body: CodeIn, request: Request, db: Session = Depends(get_db)):
    import hmac
    from ..core.security import keyed_hash
    from ..core.config import settings
    org, env, r = _dl(db, dtok)
    if r.code_attempts >= settings.CODE_MAX_ATTEMPTS: raise HTTPException(423, "Too many incorrect codes; request a new code")
    if not r.code_hash or not r.code_expires_at or r.code_expires_at < now() or not hmac.compare_digest(keyed_hash(f"dl:{r.id}", body.code.strip()), r.code_hash):
        r.code_attempts += 1
        audit.record(db, env, "authentication_failed", r.email, request, "completed-document re-access", r); db.commit()
        raise HTTPException(403, "Incorrect or expired code")
    r.code_hash = None
    audit.record(db, env, "downloaded", r.email, request, "completed document (re-authenticated by email code)", r); db.commit()
    return Response(storage().get(org.region, env.completed_key), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{env.public_id}-signed.pdf"', "Cache-Control": "no-store"})
