"""Privacy console (FR-195..199): data-subject requests and organization data export."""
import io, json, zipfile
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..models import Envelope, Recipient, Contact, DataSubjectRequest, DeletionRecord, AuditEvent, User, now
from ..services import audit, retention
from ..services.storage import storage
from .deps import Principal, perm, org_member

router = APIRouter(prefix="/privacy", tags=["privacy"])


class DSRIn(BaseModel):
    email: EmailStr
    kind: str  # access | correct | erase
    new_name: str | None = None
    new_email: EmailStr | None = None


@router.post("/dsr")
def dsr(body: DSRIn, request: Request, p: Principal = Depends(perm("privacy.manage")), db: Session = Depends(get_db)):
    email = str(body.email).lower()
    q = db.query(Recipient).join(Envelope, Envelope.id == Recipient.envelope_id).filter(Envelope.org_id == p.org.id, Recipient.email == email)
    if body.kind == "access":
        out = {"email": email, "recipients": [{"envelope": db.get(Envelope, r.envelope_id).public_id, "name": r.name, "phone": r.phone, "status": r.status,
                                                "completed_at": r.completed_at, "ip": r.completed_ip} for r in q],
               "contacts": [{"name": c.name, "email": c.email} for c in db.query(Contact).filter_by(org_id=p.org.id, email=email)]}
    elif body.kind == "correct":
        n = 0
        for r in q:
            if r.status == "completed": continue
            if body.new_name: r.name = body.new_name
            if body.new_email: r.email = str(body.new_email).lower()
            n += 1
        out = {"corrected_open_records": n, "note": "Signed (completed) records are not altered; their certificate reflects the identity at signing."}
    elif body.kind == "erase":
        out = retention.erase_subject(db, p.org, email, p.user)
        db.add(DeletionRecord(org_id=p.org.id, reason="dsr_erase", detail=json.dumps(out)))
    else:
        raise HTTPException(422, "kind must be access, correct or erase")
    db.add(DataSubjectRequest(org_id=p.org.id, email=email, kind=body.kind, outcome=json.dumps(out, default=str), requested_by=p.user.id))
    audit.admin_log(db, p.org.id, p.user, f"privacy.dsr_{body.kind}", email, req=request)
    db.commit()
    return json.loads(json.dumps(out, default=str))


@router.get("/dsr")
def dsr_list(p: Principal = Depends(perm("privacy.manage")), db: Session = Depends(get_db)):
    return [{k: getattr(d, k) for k in ("id", "email", "kind", "status", "outcome", "created_at")} for d in db.query(DataSubjectRequest).filter_by(org_id=p.org.id).order_by(DataSubjectRequest.id.desc())]


@router.get("/deletions")
def deletions(p: Principal = Depends(perm("privacy.manage")), db: Session = Depends(get_db)):
    return [{k: getattr(d, k) for k in ("id", "envelope_public_id", "reason", "detail", "created_at")} for d in db.query(DeletionRecord).filter_by(org_id=p.org.id).order_by(DeletionRecord.id.desc())]


@router.get("/export")
def org_export(request: Request, include_files: bool = True, p: Principal = Depends(perm("privacy.manage")), db: Session = Depends(get_db)):
    """Org data export (FR-169): envelopes metadata, audit trails, users and completed PDFs in one ZIP."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        envs = db.query(Envelope).filter_by(org_id=p.org.id).all()
        z.writestr("users.json", json.dumps([{"email": u.email, "name": u.full_name, "role": u.role, "active": u.is_active} for u in db.query(User).filter_by(org_id=p.org.id)], indent=1))
        meta = []
        for e in envs:
            meta.append({"id": e.public_id, "title": e.title, "status": e.status, "sent_at": e.sent_at, "completed_at": e.completed_at, "sha256": e.completed_sha256,
                         "recipients": [{"name": r.name, "email": r.email, "status": r.status, "completed_at": r.completed_at} for r in e.recipients]})
            ev = db.query(AuditEvent).filter_by(envelope_id=e.id).order_by(AuditEvent.id).all()
            z.writestr(f"audit/{e.public_id}.csv", audit.events_csv(ev))
            if include_files and e.completed_key:
                try: z.writestr(f"completed/{e.public_id}.pdf", storage().get(p.org.region, e.completed_key))
                except Exception: pass  # noqa: BLE001
        z.writestr("envelopes.json", json.dumps(meta, indent=1, default=str))
    audit.admin_log(db, p.org.id, p.user, "privacy.org_export", p.org.slug, req=request); db.commit()
    return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{p.org.slug}-export.zip"'})


# ---------- self-service requests for a staff member's own data (admin-approved) ----------
class MyReqIn(BaseModel):
    kind: str  # export | erase
    note: str | None = None


def _own_export(db, p: Principal) -> dict:
    u = p.user
    envs = db.query(Envelope).filter_by(org_id=p.org.id, owner_id=u.id).all()
    rec = db.query(Recipient).join(Envelope, Envelope.id == Recipient.envelope_id).filter(Envelope.org_id == p.org.id, Recipient.email == u.email).all()
    return {"profile": {"email": u.email, "name": u.full_name, "role": u.role, "created_at": u.created_at},
            "envelopes_sent": [{"id": e.public_id, "title": e.title, "status": e.status, "sent_at": e.sent_at, "completed_at": e.completed_at} for e in envs],
            "as_recipient": [{"envelope": db.get(Envelope, r.envelope_id).public_id, "name": r.name, "status": r.status, "completed_at": r.completed_at,
                              "consent_at": r.consent_at, "ip": r.completed_ip} for r in rec]}


@router.post("/my-requests", status_code=201)
def my_request(body: MyReqIn, request: Request, p: Principal = Depends(org_member), db: Session = Depends(get_db)):
    if body.kind not in ("export", "erase"): raise HTTPException(422, "kind must be export or erase")
    if db.query(DataSubjectRequest).filter_by(org_id=p.org.id, requested_by=p.user.id, kind=f"self_{body.kind}", status="pending").first():
        raise HTTPException(409, "You already have a pending request of this type")
    d = DataSubjectRequest(org_id=p.org.id, email=p.user.email, kind=f"self_{body.kind}", status="pending", outcome=json.dumps({"note": (body.note or "")[:500]}), requested_by=p.user.id)
    db.add(d); db.flush()
    audit.admin_log(db, p.org.id, p.user, f"privacy.self_{body.kind}_requested", p.user.email, req=request); db.commit()
    return {"id": d.id, "status": d.status}


@router.get("/my-requests")
def my_requests(p: Principal = Depends(org_member), db: Session = Depends(get_db)):
    return [{"id": d.id, "kind": d.kind, "status": d.status, "created_at": d.created_at}
            for d in db.query(DataSubjectRequest).filter_by(org_id=p.org.id, requested_by=p.user.id).order_by(DataSubjectRequest.id.desc())]


@router.get("/my-requests/{rid}/download")
def my_request_download(rid: int, p: Principal = Depends(org_member), db: Session = Depends(get_db)):
    d = db.query(DataSubjectRequest).filter_by(id=rid, org_id=p.org.id, requested_by=p.user.id, kind="self_export").first()
    if not d: raise HTTPException(404, "Request not found")
    if d.status != "completed": raise HTTPException(409, "This request has not been approved yet")
    body = json.dumps(_own_export(db, p), indent=1, default=str)
    return Response(body, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="my-data-{rid}.json"'})


class DecideIn(BaseModel):
    approve: bool
    note: str | None = None


@router.post("/dsr/{rid}/decide")
def decide(rid: int, body: DecideIn, request: Request, p: Principal = Depends(perm("privacy.manage")), db: Session = Depends(get_db)):
    d = db.query(DataSubjectRequest).filter_by(id=rid, org_id=p.org.id).first()
    if not d or not d.kind.startswith("self_"): raise HTTPException(404, "Request not found")
    if d.status != "pending": raise HTTPException(409, "Request already decided")
    out = {"decided_by": p.user.email, "note": (body.note or "")[:500]}
    if body.approve and d.kind == "self_erase":
        out.update(retention.erase_subject(db, p.org, d.email, p.user))
        u = db.query(User).filter_by(id=d.requested_by, org_id=p.org.id).first()
        if u and u.id != p.user.id:
            u.is_active = False; out["account"] = "deactivated"
        db.add(DeletionRecord(org_id=p.org.id, reason="dsr_erase", detail=json.dumps(out, default=str)))
    d.status = "completed" if body.approve else "rejected"
    d.outcome = json.dumps(out, default=str)
    audit.admin_log(db, p.org.id, p.user, f"privacy.{d.kind}_{d.status}", d.email, req=request); db.commit()
    return {"id": d.id, "status": d.status, "outcome": out}
