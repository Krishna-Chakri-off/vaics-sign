"""VAICS Sign: sequential electronic signature workflow with access codes."""
import hashlib, hmac, html, io, json, os, secrets, uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Header
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from ..config import settings, sign_settings as S
from ..database import get_db
from ..security import get_current_user
from ..models import User, now
from ..sign_models import SignDocument as Doc, SignRecipient as Rcp, SignField as Fld, SignAuditEvent as Evt, SignEmail as Mail

router = APIRouter(prefix="/sign", tags=["VAICS Sign"])
SENDER_ROLES = {"admin", "change_manager", "implementer", "requester"}
IST = timezone(timedelta(hours=5, minutes=30))
FONT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "GreatVibes-Regular.ttf")


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def code_hash(rid: int, code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"{rid}:{code}".encode(), hashlib.sha256).hexdigest()


def store_dir():
    os.makedirs(S.SIGN_STORAGE_DIR, exist_ok=True)
    return S.SIGN_STORAGE_DIR


def ip_of(req):
    return req.client.host if req and req.client else None


def audit(db, doc, event, actor, req: Request | None = None, detail=""):
    prev = db.query(Evt).filter_by(document_id=doc.id).order_by(Evt.id.desc()).first()
    ts = now(); ip = ip_of(req)
    ua = req.headers.get("user-agent", "")[:300] if req else None
    dh = doc.completed_sha256 or doc.version_hash or doc.original_sha256
    payload = json.dumps([doc.id, event, actor, ip, detail, dh, prev.entry_hash if prev else None, ts.isoformat()])
    db.add(Evt(document_id=doc.id, event=event, actor=actor, ip=ip, user_agent=ua, detail=detail, doc_sha256=dh,
               prev_hash=prev.entry_hash if prev else None, entry_hash=sha256(payload.encode()), created_at=ts))
    db.flush()


def smtp_configured():
    return bool(settings.SMTP_HOST)


def send_email(db, doc, to, kind, subject, text_body, link=None, code=None, attachment: tuple[str, bytes] | None = None):
    """Send via SMTP if configured; otherwise record in the DEV outbox. Never claims delivery without SMTP acceptance."""
    rec = Mail(document_id=doc.id, to=to, kind=kind, subject=subject, body=text_body, link=link,
               attachment=attachment[0] if attachment else None, delivery="dev_outbox")
    if not smtp_configured():
        rec.code = code  # dev only: shown in the DEV EMAIL OUTBOX page so the demo can proceed
        db.add(rec); db.flush(); return rec
    try:
        import smtplib
        from email.message import EmailMessage
        m = EmailMessage(); m["Subject"] = subject; m["From"] = settings.SMTP_FROM; m["To"] = to
        m.set_content(text_body)
        body_html = html.escape(text_body).replace("\n", "<br>")
        btn = f'<p><a href="{html.escape(link)}" style="background:{S.SIGN_ACCENT_COLOR};color:#fff;padding:8px 12px;text-decoration:none;font-weight:500">Open document</a></p>' if link else ""
        codehtml = f'<p style="font-size:22px;letter-spacing:4px;font-weight:600;color:{S.SIGN_PRIMARY_COLOR}">{code}</p>' if code else ""
        m.add_alternative(f"""<div style="font-family:'Segoe UI',Roboto,Helvetica,Arial;font-size:14px;color:#0F172A;max-width:600px">
<div style="background:{S.SIGN_PRIMARY_COLOR};color:#fff;padding:12px 16px;font-weight:600">{html.escape(S.SIGN_PRODUCT_NAME)} · {html.escape(S.SIGN_ORG_NAME)}</div>
<div style="border:1px solid #E5E7EB;padding:16px;background:#fff">{body_html}{codehtml}{btn}</div>
<div style="color:#475569;font-size:12px;padding:8px 0">This is an automated message from {html.escape(S.SIGN_PRODUCT_NAME)}.</div></div>""", subtype="html")
        if attachment:
            m.add_attachment(attachment[1], maintype="application", subtype="pdf", filename=attachment[0])
        cls = smtplib.SMTP_SSL if S.SIGN_SMTP_SSL else smtplib.SMTP
        with cls(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as s:
            if not S.SIGN_SMTP_SSL: s.starttls()
            if settings.SMTP_USER: s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(m)
        rec.delivery = "smtp_accepted"
    except Exception as e:  # noqa: BLE001
        rec.delivery, rec.error = "smtp_failed", str(e)[:300]
    db.add(rec); db.flush(); return rec


def get_doc(db, user, doc_id) -> Doc:
    d = db.get(Doc, doc_id)
    if not d or d.organization_id != user.organization_id:
        raise HTTPException(404, "Document not found")
    if user.role != "admin" and d.owner_id != user.id:
        raise HTTPException(403, "Not your document")
    return d


def can_send(user):
    if user.role not in SENDER_ROLES:
        raise HTTPException(403, "Your role cannot send documents for signature")


FIELD_KEYS = ("id", "recipient_id", "type", "page", "x", "y", "w", "h", "required", "reason", "signed_at", "field_hash")


def doc_out(db, d: Doc, full=False):
    owner = db.get(User, d.owner_id)
    out = {k: getattr(d, k) for k in ("id", "title", "description", "category", "status", "message", "original_name",
                                       "original_sha256", "version_hash", "completed_sha256", "page_count", "created_at", "updated_at", "expires_at")}
    out["owner"] = owner.full_name if owner else None
    out["owner_email"] = owner.email if owner else None
    rs = db.query(Rcp).filter_by(document_id=d.id).order_by(Rcp.order, Rcp.id).all()
    out["recipients"] = [{k: getattr(r, k) for k in ("id", "name", "email", "role", "order", "status", "signed_at", "signed_ip", "decline_reason", "code_locked", "code_attempts")} for r in rs]
    if full:
        out["fields"] = [{k: getattr(f, k) for k in FIELD_KEYS} for f in db.query(Fld).filter_by(document_id=d.id).order_by(Fld.id)]
        out["audit"] = [{k: getattr(e, k) for k in ("id", "event", "actor", "ip", "user_agent", "detail", "doc_sha256", "prev_hash", "entry_hash", "created_at")} for e in db.query(Evt).filter_by(document_id=d.id).order_by(Evt.id)]
        out["emails"] = [mail_out(m) for m in db.query(Mail).filter_by(document_id=d.id).order_by(Mail.id)]
    return out


def mail_out(m: Mail):
    return {k: getattr(m, k) for k in ("id", "document_id", "to", "kind", "subject", "body", "link", "code", "attachment", "delivery", "error", "created_at")}


def refresh_expiry(db, d: Doc):
    if d.status in ("sent", "viewed", "partially_signed") and d.expires_at and d.expires_at < now():
        d.status = "expired"; audit(db, d, "expired", "system"); db.commit()


@router.get("/branding")
def branding():
    return {"org_name": S.SIGN_ORG_NAME, "product_name": S.SIGN_PRODUCT_NAME, "primary": S.SIGN_PRIMARY_COLOR, "accent": S.SIGN_ACCENT_COLOR,
            "logo": S.SIGN_LOGO_URL, "email_mode": "smtp" if smtp_configured() else "dev_outbox"}


def scoped(db, user):
    q = db.query(Doc).filter_by(organization_id=user.organization_id)
    return q if user.role == "admin" else q.filter_by(owner_id=user.id)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    docs = scoped(db, user).all()
    for d in docs: refresh_expiry(db, d)
    counts = {s: 0 for s in ("draft", "sent", "viewed", "partially_signed", "completed", "declined", "cancelled", "expired")}
    for d in docs: counts[d.status] = counts.get(d.status, 0) + 1
    ids = [d.id for d in docs]
    recent = db.query(Evt).filter(Evt.document_id.in_(ids)).order_by(Evt.id.desc()).limit(15).all() if ids else []
    titles = {d.id: d.title for d in docs}
    return {"total": len(docs), "counts": counts, "awaiting": counts["sent"] + counts["viewed"],
            "recent": [{"document_id": e.document_id, "title": titles.get(e.document_id), "event": e.event, "actor": e.actor, "created_at": e.created_at} for e in recent]}


@router.get("/outbox")
def outbox(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ids = [d.id for d in scoped(db, user).all()]
    rows = db.query(Mail).filter(Mail.document_id.in_(ids)).order_by(Mail.id.desc()).limit(200).all() if ids else []
    return {"smtp_configured": smtp_configured(), "emails": [mail_out(m) for m in rows]}


@router.get("/documents")
def list_docs(status: str | None = None, q: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    qry = scoped(db, user)
    if status: qry = qry.filter_by(status=status)
    if q: qry = qry.filter(Doc.title.ilike(f"%{q}%"))
    docs = qry.order_by(Doc.id.desc()).all()
    for d in docs: refresh_expiry(db, d)
    return [doc_out(db, d) for d in docs]


@router.post("/documents")
async def upload(request: Request, file: UploadFile = File(...), title: str = Form(...), description: str = Form(""), category: str = Form("General"),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    can_send(user)
    data = await file.read()
    if len(data) > S.SIGN_MAX_UPLOAD_MB * 1024 * 1024: raise HTTPException(413, f"File exceeds {S.SIGN_MAX_UPLOAD_MB} MB")
    if not data.startswith(b"%PDF-"): raise HTTPException(415, "Only PDF files are accepted")
    try:
        from pypdf import PdfReader
        pages = len(PdfReader(io.BytesIO(data)).pages)
    except Exception:
        raise HTTPException(422, "PDF could not be parsed")
    path = os.path.join(store_dir(), f"{uuid.uuid4().hex}.pdf")
    with open(path, "wb") as fh: fh.write(data)
    h = sha256(data)
    d = Doc(organization_id=user.organization_id, owner_id=user.id, title=title.strip()[:200] or "Untitled", description=description, category=category,
            original_path=path, original_sha256=h, version_hash=h, original_name=(file.filename or "document.pdf")[:255], page_count=pages)
    db.add(d); db.flush()
    audit(db, d, "uploaded", user.email, request, f"{d.original_name}, {pages} page(s), sha256 {h}")
    db.commit()
    return doc_out(db, d, True)


@router.get("/documents/{doc_id}")
def detail(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = get_doc(db, user, doc_id); refresh_expiry(db, d)
    return doc_out(db, d, True)


class RcpIn(BaseModel):
    name: str
    email: EmailStr


class FldIn(BaseModel):
    recipient_index: int
    page: int = 1
    x: float
    y: float
    w: float = 0.28
    h: float = 0.09


class PrepIn(BaseModel):
    title: str | None = None
    description: str | None = None
    message: str = ""
    recipients: list[RcpIn]  # strict order = list order
    fields: list[FldIn] = []


@router.put("/documents/{doc_id}")
def prepare(doc_id: int, body: PrepIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = get_doc(db, user, doc_id)
    if d.status != "draft": raise HTTPException(409, "Only drafts can be edited")
    if body.title is not None: d.title = body.title.strip()[:200] or d.title
    if body.description is not None: d.description = body.description
    d.message, d.sequential = body.message, True
    db.query(Fld).filter_by(document_id=d.id).delete(); db.query(Rcp).filter_by(document_id=d.id).delete()
    rs = []
    for i, r in enumerate(body.recipients, start=1):
        if not r.name.strip(): raise HTTPException(422, f"Signer {i} needs a name")
        o = Rcp(document_id=d.id, name=r.name.strip()[:120], email=str(r.email).lower(), role="signer", order=i); db.add(o); rs.append(o)
    db.flush()
    for f in body.fields:
        if not (0 <= f.recipient_index < len(rs)): raise HTTPException(422, "Field assigned to unknown signer")
        if not (1 <= f.page <= d.page_count and 0 <= f.x <= 1 and 0 <= f.y <= 1 and 0.02 <= f.w <= 1 and 0.01 <= f.h <= 1 and f.x + f.w <= 1.001 and f.y + f.h <= 1.001):
            raise HTTPException(422, "Field outside the page")
        db.add(Fld(document_id=d.id, recipient_id=rs[f.recipient_index].id, type="signature", page=f.page, x=f.x, y=f.y, w=f.w, h=f.h))
    audit(db, d, "draft_saved", user.email, request, f"{len(rs)} signer(s), {len(body.fields)} signature field(s)")
    db.commit()
    return doc_out(db, d, True)


def notify_next(db, d: Doc, request, actor):
    """Issue link + separate access code to the next signer only (strict order)."""
    nxt = db.query(Rcp).filter(Rcp.document_id == d.id, Rcp.status != "signed").order_by(Rcp.order, Rcp.id).first()
    if not nxt: return None
    tok = secrets.token_urlsafe(32)
    code = "".join(secrets.choice("0123456789") for _ in range(max(6, min(8, S.SIGN_CODE_LENGTH))))
    nxt.token_hash, nxt.token_revoked = sha256(tok.encode()), False
    nxt.token_expires_at = now() + timedelta(days=S.SIGN_LINK_EXPIRY_DAYS)
    nxt.code_hash, nxt.code_attempts, nxt.code_locked = code_hash(nxt.id, code), 0, False
    nxt.code_expires_at = now() + timedelta(hours=S.SIGN_CODE_EXPIRY_HOURS)
    nxt.session_hash = None
    nxt.status = "sent"
    owner = db.get(User, d.owner_id)
    url = f"{S.SIGN_PUBLIC_BASE_URL}/sign/{tok}"
    m1 = send_email(db, d, nxt.email, "signing_link", f"[{S.SIGN_PRODUCT_NAME}] Signature requested: {d.title}",
                    f"Hello {nxt.name},\n\n{owner.full_name if owner else S.SIGN_ORG_NAME} has requested your signature on \"{d.title}\" (signer {nxt.order}).\n"
                    f"{(chr(10) + d.message + chr(10)) if d.message else ''}\nOpen the secure link below. You will also receive a separate email with your signature access code.\n\n{url}\n\nThe link expires in {S.SIGN_LINK_EXPIRY_DAYS} days.\n\n{S.SIGN_ORG_NAME}", link=url)
    m2 = send_email(db, d, nxt.email, "access_code", f"[{S.SIGN_PRODUCT_NAME}] Your signature access code",
                    f"Hello {nxt.name},\n\nYour access code to open \"{d.title}\" is shown below. It expires in {S.SIGN_CODE_EXPIRY_HOURS} hours and allows {S.SIGN_CODE_MAX_ATTEMPTS} attempts. Do not share it.\n\n{S.SIGN_ORG_NAME}", code=code)
    audit(db, d, "signer_notified", actor, request, f"signer {nxt.order} {nxt.email}; link email {m1.delivery}; code email {m2.delivery}")
    return nxt


@router.post("/documents/{doc_id}/send")
def generate(doc_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """'Generate': validates and notifies signer 1 only."""
    d = get_doc(db, user, doc_id); can_send(user)
    if d.status != "draft": raise HTTPException(409, "Already generated")
    rs = db.query(Rcp).filter_by(document_id=d.id).order_by(Rcp.order).all()
    if not rs: raise HTTPException(422, "Add at least one signer")
    for r in rs:
        if not db.query(Fld).filter_by(document_id=d.id, recipient_id=r.id).count():
            raise HTTPException(422, f"Place at least one signature field for {r.name}")
    d.status, d.expires_at = "sent", now() + timedelta(days=S.SIGN_LINK_EXPIRY_DAYS)
    audit(db, d, "generated", user.email, request, f"{len(rs)} signer(s); requester {user.email} is CC")
    notify_next(db, d, request, user.email)
    db.commit()
    return {"status": d.status, "email_mode": "smtp" if smtp_configured() else "dev_outbox"}


@router.post("/documents/{doc_id}/cancel")
def cancel(doc_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = get_doc(db, user, doc_id)
    if d.status in ("completed", "cancelled", "declined"): raise HTTPException(409, "Cannot cancel")
    d.status = "cancelled"
    for r in db.query(Rcp).filter_by(document_id=d.id): r.token_revoked = True; r.session_hash = None
    audit(db, d, "cancelled", user.email, request); db.commit()
    return doc_out(db, d)


@router.post("/documents/{doc_id}/recipients/{rid}/resend")
def resend(doc_id: int, rid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Revoke the current signer's link + code and issue new ones (also unlocks a locked-out signer)."""
    d = get_doc(db, user, doc_id)
    r = db.get(Rcp, rid)
    if not r or r.document_id != d.id or d.status not in ("sent", "viewed", "partially_signed") or r.status not in ("sent", "viewed"):
        raise HTTPException(409, "This signer is not the current signer")
    r.token_revoked = True; audit(db, d, "link_revoked", user.email, request, r.email)
    notify_next(db, d, request, user.email); db.commit()
    return {"ok": True}


def file_resp(path, name):
    with open(path, "rb") as fh: data = fh.read()
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}"', "Cache-Control": "no-store"})


@router.get("/documents/{doc_id}/file")
def original(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = get_doc(db, user, doc_id); return file_resp(d.original_path, d.original_name)


@router.get("/documents/{doc_id}/completed")
def completed(doc_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = get_doc(db, user, doc_id)
    if d.status != "completed" or not d.completed_path: raise HTTPException(409, "Not completed yet")
    audit(db, d, "downloaded", user.email, request); db.commit()
    return file_resp(d.completed_path, f"signed-{d.original_name}")


# ---------- public signer endpoints ----------
def by_token(db, token) -> tuple[Doc, Rcp]:
    r = db.query(Rcp).filter_by(token_hash=sha256(token.encode())).first()
    if not r or r.token_revoked: raise HTTPException(404, "Invalid or revoked link")
    if r.token_expires_at and r.token_expires_at < now(): raise HTTPException(410, "This signing link has expired")
    d = db.get(Doc, r.document_id); refresh_expiry(db, d)
    if d.status not in ("sent", "viewed", "partially_signed"): raise HTTPException(409, f"Document is {d.status}")
    cur = db.query(Rcp).filter(Rcp.document_id == d.id, Rcp.status != "signed").order_by(Rcp.order, Rcp.id).first()
    if not cur or cur.id != r.id: raise HTTPException(409, "It is not your turn to sign yet")
    return d, r


def by_session(db, token, session) -> tuple[Doc, Rcp]:
    d, r = by_token(db, token)
    if not session or not r.session_hash or sha256(session.encode()) != r.session_hash or (r.session_expires_at and r.session_expires_at < now()):
        raise HTTPException(401, "Enter your access code to unlock this document")
    return d, r


@router.get("/public/{token}")
def pub_info(token: str, db: Session = Depends(get_db)):
    d, r = by_token(db, token)
    return {"title": d.title, "recipient": {"name": r.name, "email": r.email, "order": r.order}, "locked": r.code_locked, "branding": branding()}


class CodeIn(BaseModel):
    code: str


@router.post("/public/{token}/unlock")
def pub_unlock(token: str, body: CodeIn, request: Request, db: Session = Depends(get_db)):
    d, r = by_token(db, token)
    if r.code_locked: raise HTTPException(423, "Too many wrong codes. Ask the sender to reissue your link and code.")
    if not r.code_hash or (r.code_expires_at and r.code_expires_at < now()): raise HTTPException(410, "Access code expired. Ask the sender to reissue.")
    if not hmac.compare_digest(code_hash(r.id, body.code.strip()), r.code_hash):
        r.code_attempts += 1
        left = S.SIGN_CODE_MAX_ATTEMPTS - r.code_attempts
        if left <= 0:
            r.code_locked = True; audit(db, d, "code_locked", r.email, request, "maximum attempts reached"); db.commit()
            raise HTTPException(423, "Too many wrong codes. Ask the sender to reissue your link and code.")
        audit(db, d, "code_failed", r.email, request, f"{left} attempt(s) left"); db.commit()
        raise HTTPException(403, f"Incorrect access code. {left} attempt(s) left.")
    sess = secrets.token_urlsafe(32)
    r.session_hash, r.session_expires_at, r.code_attempts = sha256(sess.encode()), now() + timedelta(minutes=S.SIGN_SESSION_MINUTES), 0
    audit(db, d, "code_verified", r.email, request)
    if r.status == "sent":
        r.status = "viewed"
        if d.status == "sent": d.status = "viewed"
        audit(db, d, "viewed", r.email, request)
    db.commit()
    return {"session": sess}


@router.get("/public/{token}/doc")
def pub_doc(token: str, x_sign_session: str | None = Header(None), db: Session = Depends(get_db)):
    d, r = by_session(db, token, x_sign_session)
    mine = db.query(Fld).filter_by(document_id=d.id, recipient_id=r.id).order_by(Fld.page, Fld.y, Fld.x).all()
    others = db.query(Fld).filter(Fld.document_id == d.id, Fld.recipient_id != r.id, Fld.signed_at.isnot(None)).all()
    return {"title": d.title, "message": d.message, "page_count": d.page_count, "recipient": {"name": r.name, "email": r.email, "order": r.order},
            "fields": [{k: getattr(f, k) for k in ("id", "page", "x", "y", "w", "h")} for f in mine],
            "signed_by_others": [{"page": f.page, "x": f.x, "y": f.y, "w": f.w, "h": f.h, "name": db.get(Rcp, f.recipient_id).name} for f in others],
            "branding": branding()}


@router.get("/public/{token}/file")
def pub_file(token: str, x_sign_session: str | None = Header(None), db: Session = Depends(get_db)):
    d, r = by_session(db, token, x_sign_session); return file_resp(d.original_path, d.original_name)


class SignIn(BaseModel):
    consent: bool
    reasons: dict[int, str]


@router.post("/public/{token}/sign")
def pub_sign(token: str, body: SignIn, request: Request, x_sign_session: str | None = Header(None), db: Session = Depends(get_db)):
    d, r = by_session(db, token, x_sign_session)
    if not body.consent: raise HTTPException(422, "You must consent to sign electronically")
    fields = db.query(Fld).filter_by(document_id=d.id, recipient_id=r.id).order_by(Fld.id).all()
    for f in fields:
        if not (body.reasons.get(f.id) or "").strip(): raise HTTPException(422, "A reason is required for every signature field")
    ts = now()
    for f in fields:
        f.reason, f.value, f.signed_at = body.reasons[f.id].strip()[:200], r.name, ts
        f.field_hash = sha256(f"{d.version_hash}|{r.id}|{r.email}|{r.name}|{f.id}|{ts.isoformat()}Z|{f.reason}".encode())
    d.version_hash = sha256((d.version_hash + "".join(f.field_hash for f in fields)).encode())
    r.status, r.signature_type, r.signature_data = "signed", "typed", r.name
    r.signed_at, r.signed_ip, r.token_revoked, r.session_hash = ts, ip_of(request), True, None
    audit(db, d, "signed", r.email, request, f"{len(fields)} field(s); consent given; version {d.version_hash}")
    if db.query(Rcp).filter(Rcp.document_id == d.id, Rcp.status != "signed").count():
        d.status = "partially_signed"; notify_next(db, d, request, "system")
    else:
        finalize(db, d, request)
    db.commit()
    return {"status": d.status}


@router.post("/public/{token}/decline")
def pub_decline(token: str, request: Request, reason: str = Form(""), x_sign_session: str | None = Header(None), db: Session = Depends(get_db)):
    d, r = by_session(db, token, x_sign_session)
    r.status, r.decline_reason = "declined", reason[:1000]
    d.status = "declined"
    for x in db.query(Rcp).filter_by(document_id=d.id): x.token_revoked = True; x.session_hash = None
    audit(db, d, "declined", r.email, request, reason[:300])
    owner = db.get(User, d.owner_id)
    if owner: send_email(db, d, owner.email, "declined", f"[{S.SIGN_PRODUCT_NAME}] Declined: {d.title}", f"{r.name} ({r.email}) declined \"{d.title}\".\nReason: {reason or '-'}")
    db.commit()
    return {"status": d.status}


@router.get("/public/download/{dtoken}")
def pub_download(dtoken: str, request: Request, db: Session = Depends(get_db)):
    r = db.query(Rcp).filter_by(download_hash=sha256(dtoken.encode())).first()
    if not r or (r.download_expires_at and r.download_expires_at < now()): raise HTTPException(404, "Invalid or expired download link")
    d = db.get(Doc, r.document_id)
    if d.status != "completed": raise HTTPException(409, "Not completed")
    audit(db, d, "downloaded", r.email, request, "signer download link"); db.commit()
    return file_resp(d.completed_path, f"signed-{d.original_name}")


def _fmt_times(ts: datetime):
    u = ts.replace(tzinfo=timezone.utc)
    return u.astimezone(IST).strftime("%d %b %Y %H:%M:%S IST"), u.strftime("%Y-%m-%d %H:%M:%S UTC")


def finalize(db, d: Doc, request):
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    script = "Times-Italic"
    try:
        pdfmetrics.registerFont(TTFont("VSScript", FONT)); script = "VSScript"
    except Exception:
        pass
    reader = PdfReader(d.original_path); writer = PdfWriter()
    rcps = {r.id: r for r in db.query(Rcp).filter_by(document_id=d.id)}
    fields = db.query(Fld).filter_by(document_id=d.id).all()
    blue, muted, ink = HexColor(S.SIGN_PRIMARY_COLOR), HexColor("#475569"), HexColor("#0F172A")
    for i, page in enumerate(reader.pages, start=1):
        box = page.mediabox
        w, h = float(box.width), float(box.height)
        ox, oy = float(box.left), float(box.bottom)
        buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=(w, h))
        for f in [f for f in fields if f.page == i and f.signed_at]:
            r = rcps[f.recipient_id]
            bx, by, bw, bh = f.x * w, h - (f.y + f.h) * h, f.w * w, f.h * h  # bottom-left origin
            c.setStrokeColor(blue); c.setLineWidth(0.6); c.rect(bx, by, bw, bh)
            ist, utc = _fmt_times(f.signed_at)
            lines = [(f"Name: {r.name}", "Helvetica-Bold"), (f"Reason: {f.reason}", "Helvetica"), (f"{ist} | {utc}", "Helvetica"), (f"SHA-256: {f.field_hash}", "Helvetica")]
            small = max(3.2, min(6.5, bh / 9))
            sig_h = max(6, bh - small * 1.25 * len(lines) - 4)
            fs = min(sig_h * 0.9, 40)
            while fs > 6 and pdfmetrics.stringWidth(r.name, script, fs) > bw - 6: fs -= 0.5
            c.setFillColor(blue); c.setFont(script, fs); c.drawString(bx + 3, by + bh - fs * 0.95 - 1, r.name)
            yy = by + 2 + small * 1.25 * (len(lines) - 1)
            for txt, font in lines:
                fsz = small
                while fsz > 2.5 and pdfmetrics.stringWidth(txt, font, fsz) > bw - 6: fsz -= 0.2
                c.setFillColor(ink if font.endswith("Bold") else muted); c.setFont(font, fsz); c.drawString(bx + 3, yy, txt); yy -= small * 1.25
        c.save(); buf.seek(0)
        ov = PdfReader(buf).pages[0]
        if ox or oy:
            from pypdf import Transformation
            page.merge_transformed_page(ov, Transformation().translate(ox, oy))
        else:
            page.merge_page(ov)
        writer.add_page(page)
    audit(db, d, "completed", "system", request)
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); W, H = A4
    def header():
        c.setFillColor(blue); c.rect(0, H - 60, W, 60, fill=1, stroke=0)
        c.setFillColor(HexColor("#E6007E")); c.rect(0, H - 63, W, 3, fill=1, stroke=0)
        c.setFillColor(HexColor("#FFFFFF")); c.setFont("Helvetica-Bold", 15); c.drawString(36, H - 38, f"{S.SIGN_PRODUCT_NAME} — Certificate of Completion")
    header(); y = H - 90
    def line(t, f="Helvetica", s=9, col=ink):
        nonlocal y
        if y < 50: c.showPage(); header(); y = H - 90
        c.setFillColor(col); c.setFont(f, s); c.drawString(36, y, t[:150]); y -= s + 4
    line(f"Document: {d.title}", "Helvetica-Bold", 11)
    line(f"Organization: {S.SIGN_ORG_NAME}    Envelope ID: VS-{d.id:06d}")
    owner = db.get(User, d.owner_id)
    line(f"Requester (CC): {owner.full_name if owner else '-'} <{owner.email if owner else '-'}>")
    line(f"Original file: {d.original_name} ({d.page_count} pages)  SHA-256: {d.original_sha256}", s=7.5)
    line(f"Final signed version hash: {d.version_hash}", s=7.5); y -= 4
    line("Signers (strict order)", "Helvetica-Bold", 10)
    for r in sorted(rcps.values(), key=lambda r: r.order):
        ist, utc = _fmt_times(r.signed_at)
        line(f"{r.order}. {r.name} <{r.email}> — signed {ist} / {utc} — IP {r.signed_ip or '-'}")
        for f in sorted([f for f in fields if f.recipient_id == r.id], key=lambda f: (f.page, f.y)):
            line(f"     page {f.page} @ ({f.x:.3f},{f.y:.3f}) reason: {f.reason}", s=7.5, col=muted)
            line(f"     field SHA-256: {f.field_hash}", s=6.5, col=muted)
    y -= 4; line("Audit trail (UTC, hash-chained)", "Helvetica-Bold", 10)
    for e in db.query(Evt).filter_by(document_id=d.id).order_by(Evt.id):
        line(f"{e.created_at:%Y-%m-%d %H:%M:%S}  {e.event:<16} {e.actor}  ip={e.ip or '-'}  {e.detail}", s=7)
        line(f"      entry={e.entry_hash}", s=6, col=muted)
    y -= 6
    line("Electronic signature (typed name + access-code verification + consent + audit trail). This is NOT a certificate-backed", "Helvetica-Oblique", 7.5, muted)
    line("digital signature (DSC) or Aadhaar eSign under the Information Technology Act, 2000.", "Helvetica-Oblique", 7.5, muted)
    c.save(); buf.seek(0)
    for p in PdfReader(buf).pages: writer.add_page(p)
    out = io.BytesIO(); writer.write(out); data = out.getvalue()
    path = os.path.join(store_dir(), f"{uuid.uuid4().hex}-signed.pdf")
    with open(path, "wb") as fh: fh.write(data)
    d.completed_path, d.completed_sha256, d.status = path, sha256(data), "completed"
    audit(db, d, "final_pdf_sealed", "system", request, f"completed sha256 {d.completed_sha256}")
    fname = f"signed-{d.original_name}"
    att = (fname, data) if smtp_configured() and len(data) < 9 * 1024 * 1024 else None
    if owner:
        url = f"{S.SIGN_PUBLIC_BASE_URL}/vaics-sign/{d.id}"
        send_email(db, d, owner.email, "completed", f"[{S.SIGN_PRODUCT_NAME}] Completed: {d.title}",
                   f"Hello {owner.full_name},\n\nAll signers have signed \"{d.title}\". The signed PDF{' is attached and' if att else ''} can be downloaded after logging in:\n\n{url}\n\nSigned PDF SHA-256: {d.completed_sha256}", link=url, attachment=att)
    for r in rcps.values():
        dt = secrets.token_urlsafe(32)
        r.download_hash, r.download_expires_at = sha256(dt.encode()), now() + timedelta(days=30)
        url = f"{S.SIGN_PUBLIC_BASE_URL.rstrip('/')}/sign-download/{dt}"
        send_email(db, d, r.email, "completed", f"[{S.SIGN_PRODUCT_NAME}] Completed: {d.title}",
                   f"Hello {r.name},\n\nAll parties have signed \"{d.title}\". {'The signed PDF is attached. ' if att else ''}You can also download it for 30 days here:\n\n{url}\n\nSigned PDF SHA-256: {d.completed_sha256}", link=url, attachment=att)
    audit(db, d, "completion_emails", "system", request, f"{1 + len(rcps)} recipient(s); mode {'smtp' if smtp_configured() else 'dev_outbox'}")
