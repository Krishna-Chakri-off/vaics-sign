import io, json, zipfile
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Header, Query
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field as PField
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import Session
from ..core.config import settings
from ..core.db import get_db
from ..core.security import sha256_hex, keyed_hash
from ..models import (Envelope, EnvelopeDocument, Recipient, Field, AuditEvent, User, IdempotencyKey, DeletionRecord, FIELD_TYPES, now)
from ..services import workflow as wf, audit, usage
from ..services.storage import storage
from .deps import Principal, perm, org_member, scope, envelope_access, user_groups
from .serializers import envelope_out

router = APIRouter(prefix="/envelopes", tags=["envelopes"])


def pdf_resp(data: bytes, name: str, inline=True):
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'{"inline" if inline else "attachment"}; filename="{name}"', "Cache-Control": "no-store"})


class EnvelopeIn(BaseModel):
    title: str = PField(min_length=1, max_length=200)
    message: str = ""
    visibility: str | None = None
    group_id: int | None = None
    labels: list[str] = []
    folder: str | None = None
    language: str = "en"


@router.post("", status_code=201)
def create(body: EnvelopeIn, request: Request, idempotency_key: str | None = Header(None), p: Principal = Depends(perm("envelopes.send", "envelopes:write")),
           db: Session = Depends(get_db)):
    if idempotency_key:
        prev = db.query(IdempotencyKey).filter_by(org_id=p.org.id, key=f"env:{idempotency_key}").first()
        if prev: return prev.response
    s = wf.org_settings(p.org)
    env = Envelope(org_id=p.org.id, owner_id=p.user.id, public_id=wf.public_id(), title=body.title.strip(), message=body.message,
                   visibility=body.visibility or s["default_visibility"], group_id=body.group_id, labels=body.labels, folder=body.folder, language=body.language,
                   reminder_first_days=s["reminder_first_days"], reminder_every_days=s["reminder_every_days"], is_sandbox=p.org.is_sandbox)
    db.add(env); db.flush()
    audit.record(db, env, "created", p.user.email, request, f"via {p.via}")
    out = envelope_out(db, env)
    if idempotency_key:
        db.add(IdempotencyKey(org_id=p.org.id, key=f"env:{idempotency_key}", response=json.loads(json.dumps(out, default=str))))
    db.commit()
    return out


@router.get("")
def list_envelopes(request: Request, status: str | None = None, q: str | None = None, label: str | None = None, folder: str | None = None,
                   sender: int | None = None, recipient: str | None = None, box: str = "all", date_from: str | None = None, date_to: str | None = None,
                   sort: str = "-updated_at", page: int = 1, page_size: int = Query(25, le=200),
                   p: Principal = Depends(scope("envelopes:read")), db: Session = Depends(get_db)):
    qry = db.query(Envelope).filter(Envelope.org_id == p.org.id, Envelope.deleted_at.is_(None))
    if box == "waiting_for_me":
        rids = [r.envelope_id for r in db.query(Recipient).filter(func.lower(Recipient.email) == p.user.email, Recipient.status.notin_(("completed", "declined")))]
        qry = qry.filter(Envelope.id.in_(rids or [0]), Envelope.status.in_(wf.OPEN))
    elif box == "shared":
        qry = qry.filter(Envelope.visibility == "group", Envelope.group_id.in_(user_groups(db, p) or [0]))
    elif not p.can("envelopes.view_all") or box == "mine":
        hosted = [r.envelope_id for r in db.query(Recipient).filter_by(host_user_id=p.user.id)]
        qry = qry.filter(or_(Envelope.owner_id == p.user.id, Envelope.id.in_(hosted or [0]),
                             and_(Envelope.visibility == "group", Envelope.group_id.in_(user_groups(db, p) or [0]))) if box != "mine" else Envelope.owner_id == p.user.id)
    if status == "waiting_for_others": qry = qry.filter(Envelope.status.in_(wf.OPEN))
    elif status == "expiring_soon": qry = qry.filter(Envelope.status.in_(wf.OPEN), Envelope.expires_at <= now() + timedelta(days=7))
    elif status: qry = qry.filter(Envelope.status == status)
    if q:
        like = f"%{q.lower().strip()}%"
        qry = qry.filter(or_(func.lower(Envelope.title).like(like), Envelope.public_id == q.strip().upper(), Envelope.search_text.like(like)))
    if folder: qry = qry.filter(Envelope.folder == folder)
    if sender: qry = qry.filter(Envelope.owner_id == sender)
    if recipient:
        ids = [r.envelope_id for r in db.query(Recipient).filter(or_(func.lower(Recipient.email).like(f"%{recipient.lower()}%"), func.lower(Recipient.name).like(f"%{recipient.lower()}%")))]
        qry = qry.filter(Envelope.id.in_(ids or [0]))
    if date_from: qry = qry.filter(Envelope.created_at >= datetime.fromisoformat(date_from))
    if date_to: qry = qry.filter(Envelope.created_at < datetime.fromisoformat(date_to) + timedelta(days=1))
    rows = qry.all()
    if label: rows = [e for e in rows if label in (e.labels or [])]
    for e in rows: wf.check_expiry(db, e)
    key, rev = sort.lstrip("-"), sort.startswith("-")
    if key not in ("updated_at", "created_at", "title", "status", "expires_at", "sent_at"): key = "updated_at"
    rows.sort(key=lambda e: (getattr(e, key) is None, getattr(e, key) or ""), reverse=rev)
    total = len(rows)
    rows = rows[(page - 1) * page_size: page * page_size]
    return {"total": total, "page": page, "items": [envelope_out(db, e) for e in rows]}


@router.get("/dashboard")
def dashboard(p: Principal = Depends(org_member), db: Session = Depends(get_db)):
    mine = db.query(Envelope).filter(Envelope.org_id == p.org.id, Envelope.deleted_at.is_(None))
    if not p.can("envelopes.view_all"):
        mine = mine.filter(Envelope.owner_id == p.user.id)
    envs = mine.all()
    for e in envs: wf.check_expiry(db, e)
    counts = {}
    for e in envs: counts[e.status] = counts.get(e.status, 0) + 1
    waiting_me = []
    for r in db.query(Recipient).filter(func.lower(Recipient.email) == p.user.email, Recipient.status.notin_(("completed", "declined"))):
        e = db.get(Envelope, r.envelope_id)
        if e.org_id == p.org.id and e.status in wf.OPEN and r in wf.current_step(e): waiting_me.append({"id": e.id, "public_id": e.public_id, "title": e.title})
    soon = [e for e in envs if e.status in wf.OPEN and e.expires_at and e.expires_at <= now() + timedelta(days=7)]
    ids = [e.id for e in envs]
    recent = db.query(AuditEvent).filter(AuditEvent.envelope_id.in_(ids or [0])).order_by(AuditEvent.id.desc()).limit(15).all()
    titles = {e.id: e.title for e in envs}
    return {"total": len(envs), "counts": counts, "waiting_for_me": waiting_me, "waiting_for_others": sum(counts.get(s, 0) for s in wf.OPEN),
            "expiring_soon": [{"id": e.id, "title": e.title, "expires_at": e.expires_at} for e in soon],
            "recent": [{"envelope_id": a.envelope_id, "title": titles.get(a.envelope_id), "event": a.event, "actor": a.actor, "created_at": a.created_at} for a in recent],
            "usage": usage.summary(db, p.org)}


@router.get("/{env_id}")
def get_envelope(env_id: int, p: Principal = Depends(scope("envelopes:read")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id); wf.check_expiry(db, env)
    return envelope_out(db, env, full=True)


@router.post("/{env_id}/documents")
async def upload_document(env_id: int, request: Request, file: UploadFile = File(...), p: Principal = Depends(perm("envelopes.send", "envelopes:write")),
                          db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id, write=True)
    data = await file.read()
    d = wf.add_document(db, p.org, env, file.filename or "document.pdf", data, request, p.user.email)
    usage.check_and_record(db, p.org, "storage_bytes", d.size)
    db.commit()
    return envelope_out(db, env, full=True)


@router.delete("/{env_id}/documents/{doc_id}")
def remove_document(env_id: int, doc_id: int, request: Request, p: Principal = Depends(perm("envelopes.send", "envelopes:write")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id, write=True)
    if env.status != "draft": raise HTTPException(409, "Only drafts can be changed")
    d = next((x for x in env.documents if x.id == doc_id), None)
    if not d: raise HTTPException(404, "Document not found")
    for f in [f for f in env.fields if f.document_id == d.id]: env.fields.remove(f); db.delete(f)
    env.documents.remove(d); db.delete(d)
    for i, x in enumerate(env.documents, 1): x.order = i
    env.version_hash = sha256_hex("|".join(x.sha256 for x in env.documents)) if env.documents else None
    audit.record(db, env, "document_removed", p.user.email, request, d.name)
    db.commit()
    return envelope_out(db, env, full=True)


class ReorderIn(BaseModel):
    document_ids: list[int]


@router.post("/{env_id}/documents/reorder")
def reorder(env_id: int, body: ReorderIn, p: Principal = Depends(perm("envelopes.send", "envelopes:write")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id, write=True)
    if env.status != "draft": raise HTTPException(409, "Only drafts can be changed")
    if sorted(body.document_ids) != sorted(d.id for d in env.documents): raise HTTPException(422, "Provide all document ids")
    for i, did in enumerate(body.document_ids, 1): next(d for d in env.documents if d.id == did).order = i
    db.commit()
    return envelope_out(db, env, full=True)


@router.get("/{env_id}/documents/{doc_id}/file")
def document_file(env_id: int, doc_id: int, p: Principal = Depends(scope("envelopes:read")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id)
    d = next((x for x in env.documents if x.id == doc_id), None)
    if not d: raise HTTPException(404, "Document not found")
    if env.purged_at: raise HTTPException(410, "Document content was purged under the retention policy")
    return pdf_resp(wf.doc_bytes(p.org, d), d.name)


class RecipientIn(BaseModel):
    client_id: str | None = None  # used to link fields in the same request
    id: int | None = None
    role_name: str | None = None
    type: str = "signer"
    name: str = PField(min_length=1, max_length=120)
    email: EmailStr
    phone: str | None = None
    order: int = PField(1, ge=1, le=100)
    language: str = "en"
    private_message: str = ""
    auth_method: str | None = None
    access_code: str | None = None  # sender-set code shared outside the platform
    host_user_id: int | None = None
    signature_type: str = "electronic"


class FieldIn(BaseModel):
    recipient: str | int  # client_id or index
    document_id: int
    type: str = "signature"
    page: int = 1
    x: float
    y: float
    w: float = 0.28
    h: float = 0.09
    required: bool = True
    read_only: bool = False
    reason_required: bool = True
    label: str | None = None
    tooltip: str | None = None
    default_value: str | None = None
    options: list[str] = []
    validation: str | None = None
    regex: str | None = None
    font_size: float = 10
    group_name: str | None = None
    condition: dict = {}
    formula: str | None = None


class PrepareIn(BaseModel):
    title: str | None = None
    message: str | None = None
    language: str | None = None
    visibility: str | None = None
    group_id: int | None = None
    labels: list[str] | None = None
    folder: str | None = None
    expires_at: str | None = None
    reminder_first_days: int | None = None
    reminder_every_days: int | None = None
    sender_notify: dict | None = None
    brand: dict | None = None
    recipients: list[RecipientIn] | None = None
    fields: list[FieldIn] | None = None


RTYPES = ("signer", "approver", "viewer", "cc", "in_person", "witness", "editor")


def apply_prepare(db, p: Principal, env: Envelope, body: PrepareIn):
    s = wf.org_settings(p.org)
    for k in ("title", "message", "language", "visibility", "group_id", "labels", "folder", "reminder_first_days", "reminder_every_days", "sender_notify", "brand"):
        v = getattr(body, k)
        if v is not None: setattr(env, k, v)
    if body.expires_at: env.expires_at = datetime.fromisoformat(body.expires_at.replace("Z", ""))
    if body.brand is not None and body.brand: usage.require_feature(p.org, "branding", "Custom branding")
    if body.recipients is not None:
        for f in list(env.fields): env.fields.remove(f); db.delete(f)
        for r in list(env.recipients): env.recipients.remove(r); db.delete(r)
        db.flush()
        mapping = {}
        for i, ri in enumerate(body.recipients):
            if ri.type not in RTYPES: raise HTTPException(422, f"Unknown recipient type {ri.type}")
            if ri.type in ("witness", "editor"):
                usage.require_feature(p.org, "advanced_roles", f"Recipient role '{ri.type}'")
            if ri.type == "in_person":
                usage.require_feature(p.org, "in_person", "In-person signing")
                host = db.get(User, ri.host_user_id) if ri.host_user_id else None
                if not host or host.org_id != p.org.id: raise HTTPException(422, "In-person signer needs a host from your organization")
            auth = ri.auth_method or s["default_auth"]
            if ri.type == "in_person": auth = "none"
            r = Recipient(envelope_id=env.id, role_name=ri.role_name, type=ri.type, name=ri.name.strip(), email=str(ri.email).lower(), phone=ri.phone, order=ri.order,
                          language=ri.language, private_message=ri.private_message, auth_method=auth, host_user_id=ri.host_user_id, signature_type=ri.signature_type)
            if ri.access_code:
                if not ri.access_code.isdigit() or not 6 <= len(ri.access_code) <= 8: raise HTTPException(422, "Access codes must be 6 to 8 digits")
                r.sender_set_code = True
            env.recipients.append(r); db.flush()
            if ri.access_code:
                r.code_hash = keyed_hash(f"ac:{r.id}", ri.access_code)
                r.code_expires_at = None
            mapping[ri.client_id or str(i)] = r; mapping[str(i)] = r
    if body.fields is not None:
        if body.recipients is None:
            for f in list(env.fields): env.fields.remove(f); db.delete(f)
            mapping = {str(i): r for i, r in enumerate(env.recipients)} | {str(r.id): r for r in env.recipients}
        docs = {d.id: d for d in env.documents}
        for fi in body.fields:
            r = mapping.get(str(fi.recipient))
            if not r: raise HTTPException(422, f"Field refers to unknown recipient {fi.recipient}")
            if fi.type not in FIELD_TYPES: raise HTTPException(422, f"Unknown field type {fi.type}")
            d = docs.get(fi.document_id)
            if not d: raise HTTPException(422, "Field refers to unknown document")
            if not (1 <= fi.page <= len(d.pages)): raise HTTPException(422, "Field page out of range")
            if not (0 <= fi.x <= 1 and 0 <= fi.y <= 1 and 0.005 <= fi.w <= 1 and 0.005 <= fi.h <= 1 and fi.x + fi.w <= 1.001 and fi.y + fi.h <= 1.001):
                raise HTTPException(422, "Field must be inside the page")
            if fi.type in ("signature", "initials") and r.type not in ("signer", "in_person", "witness"):
                raise HTTPException(422, f"{r.type} recipients cannot have signature fields")
            env.fields.append(Field(envelope_id=env.id, document_id=d.id, recipient_id=r.id, **fi.model_dump(exclude={"recipient", "document_id"})))
    wf.reindex(env)


@router.put("/{env_id}")
def prepare(env_id: int, body: PrepareIn, request: Request, p: Principal = Depends(perm("envelopes.send", "envelopes:write")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id, write=True)
    if env.status != "draft": raise HTTPException(409, "Only drafts can be edited; use correct for sent envelopes")
    apply_prepare(db, p, env, body)
    audit.record(db, env, "draft_saved", p.user.email, request, f"{len(env.recipients)} recipient(s), {len(env.fields)} field(s)")
    db.commit()
    return envelope_out(db, env, full=True)


@router.post("/{env_id}/send")
def send(env_id: int, request: Request, p: Principal = Depends(perm("envelopes.send", "envelopes:write")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id, write=True)
    wf.send(db, p.org, env, p.user, request)
    db.commit()
    from ..services.notify import smtp_configured
    return {**envelope_out(db, env), "email_mode": "smtp" if smtp_configured() else "dev_outbox"}


class ReasonIn(BaseModel):
    reason: str


@router.post("/{env_id}/void")
def void(env_id: int, body: ReasonIn, request: Request, p: Principal = Depends(perm("envelopes.send", "envelopes:write")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id, write=True)
    wf.void(db, p.org, env, p.user, body.reason, request); db.commit()
    return envelope_out(db, env)


class CorrectIn(BaseModel):
    message: str | None = None
    expires_at: str | None = None
    recipients: list[dict] = []
    fields: list[dict] = []


@router.post("/{env_id}/correct")
def correct(env_id: int, body: CorrectIn, request: Request, p: Principal = Depends(perm("envelopes.send", "envelopes:write")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id, write=True)
    wf.correct(db, p.org, env, p.user, body.model_dump(), request); db.commit()
    return envelope_out(db, env, full=True)


class ReissueIn(BaseModel):
    access_code: str | None = None


@router.post("/{env_id}/recipients/{rid}/reissue")
def reissue(env_id: int, rid: int, request: Request, body: ReissueIn | None = None, p: Principal = Depends(perm("envelopes.send", "envelopes:write")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id, write=True)
    r = next((x for x in env.recipients if x.id == rid), None)
    if not r: raise HTTPException(404, "Recipient not found")
    code = (body.access_code if body else None)
    if code and (not code.isdigit() or not 6 <= len(code) <= 8): raise HTTPException(422, "Access codes must be 6 to 8 digits")
    wf.reissue(db, p.org, env, r, p.user, request, code); db.commit()
    return envelope_out(db, env)


@router.post("/{env_id}/remind")
def remind(env_id: int, request: Request, p: Principal = Depends(perm("envelopes.send", "envelopes:write")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id, write=True)
    if env.status not in wf.OPEN: raise HTTPException(409, "Envelope is not in progress")
    n = sum(wf.remind(db, p.org, env, r, request, p.user.email) for r in wf.current_step(env))
    db.commit()
    return {"reminded": n}


class ExtendIn(BaseModel):
    days: int = PField(ge=1, le=365)


@router.post("/{env_id}/extend")
def extend(env_id: int, body: ExtendIn, request: Request, p: Principal = Depends(perm("envelopes.send", "envelopes:write")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id, write=True)
    if env.status not in wf.OPEN and env.status != "expired": raise HTTPException(409, "Only open or expired envelopes can be extended")
    base = max(env.expires_at or now(), now())
    env.expires_at, env.expiry_warned = base + timedelta(days=body.days), False
    if env.status == "expired":
        env.status = "partially_signed" if any(r.status == "completed" for r in env.recipients) else "sent"
        for r in wf.current_step(env): r.status = "created"
        wf.route(db, p.org, env, request)
    audit.record(db, env, "expiry_extended", p.user.email, request, f"new expiry {env.expires_at:%Y-%m-%d}")
    db.commit()
    return envelope_out(db, env)


@router.post("/{env_id}/duplicate", status_code=201)
def duplicate(env_id: int, request: Request, p: Principal = Depends(perm("envelopes.send", "envelopes:write")), db: Session = Depends(get_db)):
    src = envelope_access(db, p, env_id)
    env = Envelope(org_id=p.org.id, owner_id=p.user.id, public_id=wf.public_id(), title=f"Copy of {src.title}"[:200], message=src.message, visibility=src.visibility,
                   group_id=src.group_id, labels=list(src.labels or []), folder=src.folder, language=src.language, reminder_first_days=src.reminder_first_days,
                   reminder_every_days=src.reminder_every_days, brand=dict(src.brand or {}), is_sandbox=p.org.is_sandbox)
    db.add(env); db.flush()
    dmap, rmap = {}, {}
    for d in src.documents:
        nd = EnvelopeDocument(envelope_id=env.id, order=d.order, name=d.name, source_name=d.source_name, source_type=d.source_type, storage_key=d.storage_key,
                              sha256=d.sha256, source_sha256=d.source_sha256, size=d.size, pages=d.pages, text=d.text)
        env.documents.append(nd); db.flush(); dmap[d.id] = nd.id
    for r in src.recipients:
        nr = Recipient(envelope_id=env.id, role_name=r.role_name, type=r.type, name=r.name, email=r.email, phone=r.phone, order=r.order, language=r.language,
                       private_message=r.private_message, auth_method=r.auth_method if not r.sender_set_code else "access_code", host_user_id=r.host_user_id, signature_type=r.signature_type)
        env.recipients.append(nr); db.flush(); rmap[r.id] = nr.id
    for f in src.fields:
        env.fields.append(Field(envelope_id=env.id, document_id=dmap[f.document_id], recipient_id=rmap[f.recipient_id], type=f.type, page=f.page, x=f.x, y=f.y, w=f.w, h=f.h,
                                required=f.required, read_only=f.read_only, reason_required=f.reason_required, label=f.label, tooltip=f.tooltip, default_value=f.default_value,
                                options=f.options, validation=f.validation, regex=f.regex, font_size=f.font_size, group_name=f.group_name, condition=f.condition, formula=f.formula))
    env.version_hash = sha256_hex("|".join(d.sha256 for d in env.documents)) if env.documents else None
    wf.reindex(env)
    audit.record(db, env, "created", p.user.email, request, f"duplicated from {src.public_id}")
    db.commit()
    return envelope_out(db, env, full=True)


@router.delete("/{env_id}")
def delete(env_id: int, request: Request, p: Principal = Depends(perm("envelopes.send", "envelopes:write")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id, write=True)
    if env.status in wf.OPEN: raise HTTPException(409, "Void the envelope before deleting it")
    if env.legal_hold: raise HTTPException(423, "Envelope is on legal hold")
    if env.status == "completed":
        keep = int(wf.org_settings(p.org)["retention"]["completed_days"])
        if env.completed_at and env.completed_at > now() - timedelta(days=keep) and wf.org_settings(p.org).get("block_delete_in_retention", True):
            raise HTTPException(423, f"Completed envelopes are retained for {keep} days by your organization's policy")
    from ..services.retention import purge_envelope
    purge_envelope(db, p.org, env, "user_delete", p.user.email, request)
    env.deleted_at = now()
    db.commit()
    return {"deleted": True}


class HoldIn(BaseModel):
    hold: bool


@router.post("/{env_id}/legal-hold")
def legal_hold(env_id: int, body: HoldIn, request: Request, p: Principal = Depends(perm("privacy.manage")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id)
    env.legal_hold = body.hold
    audit.record(db, env, "legal_hold_on" if body.hold else "legal_hold_off", p.user.email, request)
    audit.admin_log(db, p.org.id, p.user, "envelope.legal_hold", env.public_id, after={"hold": body.hold}, req=request)
    db.commit()
    return {"legal_hold": env.legal_hold}


# ---------- completed outputs ----------
def _completed(env):
    if env.purged_at: raise HTTPException(410, "Documents were purged under the retention policy")
    if env.status != "completed" or not env.completed_key: raise HTTPException(409, "Envelope is not completed")


@router.get("/{env_id}/completed")
def completed(env_id: int, request: Request, mode: str = "combined", certificate: bool = True, document_id: int | None = None,
              p: Principal = Depends(scope("envelopes:read")), db: Session = Depends(get_db)):
    """mode=combined (sealed PDF incl. certificate) | separate (one stamped document, document_id required, unsealed)"""
    env = envelope_access(db, p, env_id); _completed(env)
    st = storage()
    if mode == "combined" and certificate:
        data, name = st.get(p.org.region, env.completed_key), f"{env.public_id}-signed.pdf"
    else:
        from pypdf import PdfReader, PdfWriter
        full = PdfReader(io.BytesIO(st.get(p.org.region, env.completed_key)))
        w = PdfWriter(); idx = 0
        for d in env.documents:
            n = len(d.pages)
            if mode == "combined" or d.id == document_id:
                for pg in full.pages[idx: idx + n]: w.add_page(pg)
            idx += n
        if mode == "separate" and certificate:
            for pg in full.pages[idx:]: w.add_page(pg)
        if not w.pages: raise HTTPException(404, "Document not found")
        b = io.BytesIO(); w.write(b); data = b.getvalue(); name = f"{env.public_id}-{document_id or 'documents'}.pdf"
    audit.record(db, env, "downloaded", p.user.email, request, f"{mode}; certificate={certificate}"); db.commit()
    return pdf_resp(data, name, inline=False)


@router.get("/{env_id}/certificate")
def certificate(env_id: int, request: Request, p: Principal = Depends(scope("envelopes:read")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id); _completed(env)
    audit.record(db, env, "downloaded", p.user.email, request, "certificate"); db.commit()
    return pdf_resp(storage().get(p.org.region, env.certificate_key), f"{env.public_id}-certificate.pdf")


@router.get("/{env_id}/audit")
def audit_trail(env_id: int, format: str = "json", p: Principal = Depends(perm("audit.view", "audit:read")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id)
    events = db.query(AuditEvent).filter_by(envelope_id=env.id).order_by(AuditEvent.id).all()
    ok, bad = audit.verify_chain(events)
    if format == "csv":
        return Response(audit.events_csv(events), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{env.public_id}-audit.csv"'})
    if format == "pdf":
        return pdf_resp(audit_pdf(env, events, ok), f"{env.public_id}-audit.pdf", inline=False)
    return {"chain_valid": ok, "broken_at": bad, "events": [{k: getattr(e, k) for k in ("id", "event", "actor", "recipient_id", "ip", "user_agent", "location", "detail", "doc_hash", "prev_hash", "entry_hash", "created_at")} for e in events]}


def audit_pdf(env, events, ok) -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.colors import HexColor
    from ..services.pdfstamp import _fonts
    _fonts()
    b = io.BytesIO(); c = canvas.Canvas(b, pagesize=landscape(A4)); W, H = landscape(A4)
    def head():
        c.setFillColor(HexColor("#0D47A1")); c.rect(0, H - 40, W, 40, fill=1, stroke=0); c.setFillColor(HexColor("#FFFFFF")); c.setFont("VSSans-Bold", 12)
        c.drawString(30, H - 26, f"Audit trail — {env.public_id} — {env.title[:80]}"); c.setFont("VSSans", 8); c.drawRightString(W - 30, H - 26, f"hash chain {'VALID' if ok else 'BROKEN'}")
        return H - 58
    y = head()
    for e in events:
        if y < 40: c.showPage(); y = head()
        c.setFillColor(HexColor("#0F172A")); c.setFont("VSSans", 7)
        c.drawString(30, y, f"{e.created_at:%Y-%m-%d %H:%M:%S} UTC  {e.event:<22} {e.actor:<34} ip={e.ip or '-':<16} {e.detail[:110]}")
        c.setFillColor(HexColor("#475569")); c.setFont("VSSans", 5.5); c.drawString(40, y - 8, f"entry {e.entry_hash}  prev {e.prev_hash or '-'}  doc {e.doc_hash or '-'}"); y -= 19
    c.save(); return b.getvalue()


@router.get("/{env_id}/evidence")
def evidence(env_id: int, request: Request, p: Principal = Depends(perm("audit.view", "audit:read")), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id); _completed(env)
    events = db.query(AuditEvent).filter_by(envelope_id=env.id).order_by(AuditEvent.id).all()
    ok, _ = audit.verify_chain(events)
    st = storage(); buf = io.BytesIO()
    signed = st.get(p.org.region, env.completed_key)
    manifest = {"envelope_id": env.public_id, "title": env.title, "completed_at": env.completed_at.isoformat() + "Z", "sealed": env.sealed,
                "completed_sha256": env.completed_sha256, "version_hash": env.version_hash, "audit_chain_valid": ok,
                "documents": [{"name": d.name, "original_sha256": d.sha256, "uploaded_sha256": d.source_sha256} for d in env.documents],
                "generated_at": now().isoformat() + "Z", "generated_by": p.user.email}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{env.public_id}-signed.pdf", signed)
        z.writestr(f"{env.public_id}-certificate.pdf", st.get(p.org.region, env.certificate_key))
        for d in env.documents: z.writestr(f"originals/{d.order:02d}-{d.name}", wf.doc_bytes(p.org, d))
        z.writestr("audit.csv", audit.events_csv(events))
        z.writestr("audit.pdf", audit_pdf(env, events, ok))
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        z.writestr("SHA256SUMS.txt", f"{env.completed_sha256}  {env.public_id}-signed.pdf\n" + "".join(f"{d.sha256}  originals/{d.order:02d}-{d.name}\n" for d in env.documents))
    audit.record(db, env, "downloaded", p.user.email, request, "evidence package"); db.commit()
    return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{env.public_id}-evidence.zip"'})


# ---------- in-person ----------
class InPersonIn(BaseModel):
    id_type: str = PField(min_length=2, max_length=40)
    id_number: str | None = None
    confirmed: bool


@router.post("/{env_id}/recipients/{rid}/in-person")
def start_in_person(env_id: int, rid: int, body: InPersonIn, request: Request, p: Principal = Depends(org_member), db: Session = Depends(get_db)):
    env = envelope_access(db, p, env_id)
    r = next((x for x in env.recipients if x.id == rid), None)
    if not r or r.type != "in_person": raise HTTPException(404, "In-person recipient not found")
    if r.host_user_id != p.user.id: raise HTTPException(403, "Only the assigned host can start this session")
    if not body.confirmed: raise HTTPException(422, "Confirm that you verified the signer's identity")
    if r not in wf.current_step(env) or env.status not in wf.OPEN: raise HTTPException(409, "It is not this signer's turn")
    from ..core.security import random_token
    tok, sess = random_token(32), random_token(32)
    r.token_hash, r.token_revoked, r.session_hash, r.session_last_seen, r.status = sha256_hex(tok), False, sha256_hex(sess), now(), "authenticated"
    r.id_verification = {"id_type": body.id_type, "id_last4": (body.id_number or "")[-4:], "host": p.user.email, "verified_at": now().isoformat() + "Z"}
    audit.record(db, env, "in_person_started", p.user.email, request, f"host verified {r.name}: {body.id_type} ****{(body.id_number or '')[-4:]}", r)
    audit.record(db, env, "authenticated", r.email, request, "method: in-person host verification", r)
    db.commit()
    return {"token": tok, "session": sess, "kiosk_url": f"/s/{tok}?kiosk=1"}
