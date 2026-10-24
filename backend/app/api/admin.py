"""Org Admin console: users, invitations, groups, settings, branding, audit log, contacts, outbox, notifications."""
import base64, csv, io, json, secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field as PField
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ..core.config import settings
from ..core.db import get_db
from ..core.permissions import ROLES
from ..core.security import sha256_hex, random_token
from ..models import (User, Invitation, OneTimeToken, Group, Contact, AdminAuditLog, EmailLog, Notification,
                      Envelope, Template, UserSession, now)
from ..services import audit, notify
from ..services.workflow import org_settings, DEFAULT_ORG_SETTINGS
from .auth import issue_token, user_out
from .deps import Principal, perm, org_member

router = APIRouter(prefix="/org", tags=["organization admin"])


def u_out(u: User):
    return {k: getattr(u, k) for k in ("id", "email", "full_name", "title", "role", "is_active", "email_verified", "mfa_enabled", "last_login_at", "created_at")}


@router.get("/users")
def users(p: Principal = Depends(org_member), db: Session = Depends(get_db)):
    return [u_out(u) for u in db.query(User).filter_by(org_id=p.org.id).order_by(User.full_name)]


class InviteIn(BaseModel):
    email: EmailStr
    role: str = "sender"


@router.post("/invitations", status_code=201)
def invite(body: InviteIn, request: Request, p: Principal = Depends(perm("users.manage")), db: Session = Depends(get_db)):
    if body.role not in ROLES: raise HTTPException(422, "Unknown role")
    email = str(body.email).lower()
    if db.query(User).filter_by(email=email).first(): raise HTTPException(409, "A user with this email already exists")
    raw, t = issue_token(db, "invite", hours=settings.INVITE_DAYS * 24, org_id=p.org.id, email=email, data={"role": body.role})
    inv = Invitation(org_id=p.org.id, email=email, role=body.role, token_id=t.id, invited_by=p.user.id); db.add(inv)
    notify.send_email(db, org=p.org, to=email, kind="invitation", subject=f"{p.user.full_name} invited you to {p.org.name} on VAICS Sign",
                      body=f"You have been invited to join {p.org.name} as {body.role.replace('_', ' ')}. The invitation expires in {settings.INVITE_DAYS} days.",
                      link=f"{settings.PUBLIC_APP_URL}/invite/{raw}")
    audit.admin_log(db, p.org.id, p.user, "user.invited", email, after={"role": body.role}, req=request)
    db.commit()
    return {"id": inv.id, "email": email, "status": inv.status}


@router.get("/invitations")
def invitations(p: Principal = Depends(perm("users.manage")), db: Session = Depends(get_db)):
    out = []
    for i in db.query(Invitation).filter_by(org_id=p.org.id).order_by(Invitation.id.desc()):
        t = db.get(OneTimeToken, i.token_id)
        if i.status == "pending" and t.expires_at < now(): i.status = "expired"
        out.append({"id": i.id, "email": i.email, "role": i.role, "status": i.status, "expires_at": t.expires_at, "created_at": i.created_at})
    db.commit()
    return out


@router.post("/invitations/{inv_id}/resend")
def resend_invite(inv_id: int, request: Request, p: Principal = Depends(perm("users.manage")), db: Session = Depends(get_db)):
    inv = db.get(Invitation, inv_id)
    if not inv or inv.org_id != p.org.id: raise HTTPException(404, "Invitation not found")
    if inv.status == "accepted": raise HTTPException(409, "Already accepted")
    db.get(OneTimeToken, inv.token_id).revoked = True
    raw, t = issue_token(db, "invite", hours=settings.INVITE_DAYS * 24, org_id=p.org.id, email=inv.email, data={"role": inv.role})
    inv.token_id, inv.status = t.id, "pending"
    notify.send_email(db, org=p.org, to=inv.email, kind="invitation", subject=f"Reminder: join {p.org.name} on VAICS Sign",
                      body=f"You have been invited to join {p.org.name}.", link=f"{settings.PUBLIC_APP_URL}/invite/{raw}")
    audit.admin_log(db, p.org.id, p.user, "user.invite_resent", inv.email, req=request)
    db.commit()
    return {"status": inv.status}


@router.delete("/invitations/{inv_id}")
def revoke_invite(inv_id: int, request: Request, p: Principal = Depends(perm("users.manage")), db: Session = Depends(get_db)):
    inv = db.get(Invitation, inv_id)
    if not inv or inv.org_id != p.org.id: raise HTTPException(404, "Invitation not found")
    inv.status = "revoked"; db.get(OneTimeToken, inv.token_id).revoked = True
    audit.admin_log(db, p.org.id, p.user, "user.invite_revoked", inv.email, req=request)
    db.commit()
    return {"status": "revoked"}


class UserPatch(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    full_name: str | None = None
    title: str | None = None


def _user(db, p, uid) -> User:
    u = db.get(User, uid)
    if not u or u.org_id != p.org.id: raise HTTPException(404, "User not found")
    return u


@router.patch("/users/{uid}")
def update_user(uid: int, body: UserPatch, request: Request, p: Principal = Depends(perm("users.manage")), db: Session = Depends(get_db)):
    u = _user(db, p, uid)
    before = u_out(u)
    if body.role is not None:
        if body.role not in ROLES: raise HTTPException(422, "Unknown role")
        if u.id == p.user.id and body.role != "org_admin": raise HTTPException(409, "You cannot remove your own admin role")
        u.role = body.role
    if body.is_active is not None:
        if u.id == p.user.id: raise HTTPException(409, "You cannot deactivate yourself")
        u.is_active = body.is_active
        if not body.is_active:
            for s in db.query(UserSession).filter_by(user_id=u.id): s.revoked = True
    for k in ("full_name", "title"):
        if getattr(body, k) is not None: setattr(u, k, getattr(body, k))
    audit.admin_log(db, p.org.id, p.user, "user.updated", u.email, before=before, after=u_out(u), req=request)
    db.commit()
    return json.loads(json.dumps(u_out(u), default=str))


class TransferIn(BaseModel):
    to_user_id: int


@router.post("/users/{uid}/transfer")
def transfer(uid: int, body: TransferIn, request: Request, p: Principal = Depends(perm("users.manage")), db: Session = Depends(get_db)):
    src, dst = _user(db, p, uid), _user(db, p, body.to_user_id)
    n_env = db.query(Envelope).filter_by(org_id=p.org.id, owner_id=src.id).update({"owner_id": dst.id})
    n_tpl = db.query(Template).filter_by(org_id=p.org.id, owner_id=src.id).update({"owner_id": dst.id})
    audit.admin_log(db, p.org.id, p.user, "user.transferred", src.email, after={"to": dst.email, "envelopes": n_env, "templates": n_tpl}, req=request)
    db.commit()
    return {"envelopes": n_env, "templates": n_tpl}


@router.delete("/users/{uid}")
def delete_user(uid: int, request: Request, p: Principal = Depends(perm("users.manage")), db: Session = Depends(get_db)):
    u = _user(db, p, uid)
    if u.id == p.user.id: raise HTTPException(409, "You cannot delete yourself")
    if db.query(Envelope).filter_by(owner_id=u.id).count() or db.query(Template).filter_by(owner_id=u.id).count():
        raise HTTPException(409, "Transfer this user's envelopes and templates first")
    before = u_out(u)
    u.is_active, u.email, u.full_name, u.password_hash, u.mfa_secret = False, f"deleted-{u.id}-{secrets.token_hex(4)}@deleted.invalid", "Deleted user", None, None
    for s in db.query(UserSession).filter_by(user_id=u.id): s.revoked = True
    audit.admin_log(db, p.org.id, p.user, "user.deleted", before["email"], before=before, req=request)
    db.commit()
    return {"deleted": True}


# ---------- groups ----------
class GroupIn(BaseModel):
    name: str
    member_ids: list[int] = []


@router.get("/groups")
def groups(p: Principal = Depends(org_member), db: Session = Depends(get_db)):
    return [{"id": g.id, "name": g.name, "member_ids": g.member_ids} for g in db.query(Group).filter_by(org_id=p.org.id)]


@router.post("/groups", status_code=201)
def create_group(body: GroupIn, request: Request, p: Principal = Depends(perm("users.manage")), db: Session = Depends(get_db)):
    ids = [u.id for u in db.query(User).filter(User.org_id == p.org.id, User.id.in_(body.member_ids or [0]))]
    g = Group(org_id=p.org.id, name=body.name, member_ids=ids); db.add(g); db.flush()
    audit.admin_log(db, p.org.id, p.user, "group.created", body.name, after={"members": ids}, req=request); db.commit()
    return {"id": g.id, "name": g.name, "member_ids": g.member_ids}


@router.put("/groups/{gid}")
def update_group(gid: int, body: GroupIn, request: Request, p: Principal = Depends(perm("users.manage")), db: Session = Depends(get_db)):
    g = db.get(Group, gid)
    if not g or g.org_id != p.org.id: raise HTTPException(404, "Group not found")
    before = {"name": g.name, "members": g.member_ids}
    g.name, g.member_ids = body.name, [u.id for u in db.query(User).filter(User.org_id == p.org.id, User.id.in_(body.member_ids or [0]))]
    audit.admin_log(db, p.org.id, p.user, "group.updated", g.name, before=before, after={"name": g.name, "members": g.member_ids}, req=request); db.commit()
    return {"id": g.id, "name": g.name, "member_ids": g.member_ids}


@router.delete("/groups/{gid}")
def delete_group(gid: int, request: Request, p: Principal = Depends(perm("users.manage")), db: Session = Depends(get_db)):
    g = db.get(Group, gid)
    if not g or g.org_id != p.org.id: raise HTTPException(404, "Group not found")
    db.query(Envelope).filter_by(group_id=g.id).update({"group_id": None, "visibility": "private"})
    db.query(Template).filter_by(group_id=g.id).update({"group_id": None, "sharing": "private"})
    db.delete(g); audit.admin_log(db, p.org.id, p.user, "group.deleted", g.name, req=request); db.commit()
    return {"deleted": True}


# ---------- settings & branding ----------
@router.get("/settings")
def get_settings(p: Principal = Depends(org_member)):
    o = p.org
    return {"settings": org_settings(o), "branding": notify.brand_of(o), "organization": {"name": o.name, "country": o.country, "region": o.region,
            "status": o.status, "slug": o.slug}}


class SettingsIn(BaseModel):
    settings: dict | None = None
    organization: dict | None = None


ALLOWED_ORG_FIELDS = {"name"}


@router.put("/settings")
def put_settings(body: SettingsIn, request: Request, p: Principal = Depends(perm("settings.manage")), db: Session = Depends(get_db)):
    before = {"settings": dict(p.org.settings or {})}
    if body.settings:
        bad = set(body.settings) - set(DEFAULT_ORG_SETTINGS) - {"access_code_channel", "block_delete_in_retention"}
        if bad: raise HTTPException(422, f"Unknown settings: {', '.join(sorted(bad))}")
        new = {**(p.org.settings or {}), **body.settings}
        if int(new.get("envelope_expiry_days", 120)) < 1: raise HTTPException(422, "Expiry must be at least 1 day")
        p.org.settings = new
    if body.organization:
        for k, v in body.organization.items():
            if k in ALLOWED_ORG_FIELDS: setattr(p.org, k, v)
    audit.admin_log(db, p.org.id, p.user, "org.settings_updated", p.org.slug, before=before, after={"settings": p.org.settings, "organization": body.organization}, req=request)
    db.commit()
    return get_settings(p)


class BrandingIn(BaseModel):
    product_name: str | None = None
    primary: str | None = PField(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    accent: str | None = PField(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    email_footer: str | None = None
    reply_to: EmailStr | None = None
    profiles: list[dict] | None = None  # multiple brand profiles (FR-042)


@router.put("/branding")
def put_branding(body: BrandingIn, request: Request, p: Principal = Depends(perm("settings.manage")), db: Session = Depends(get_db)):
    before = dict(p.org.branding or {})
    p.org.branding = {**before, **body.model_dump(exclude_none=True, mode="json")}
    audit.admin_log(db, p.org.id, p.user, "org.branding_updated", p.org.slug, before=before, after=p.org.branding, req=request)
    db.commit()
    return notify.brand_of(p.org)


@router.post("/branding/logo")
async def upload_logo(request: Request, file: UploadFile = File(...), p: Principal = Depends(perm("settings.manage")), db: Session = Depends(get_db)):
    data = await file.read()
    if len(data) > 512 * 1024: raise HTTPException(413, "Logo must be under 512 KB")
    mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg" if data.startswith(b"\xff\xd8") else None
    if not mime: raise HTTPException(415, "Logo must be PNG or JPEG")
    p.org.branding = {**(p.org.branding or {}), "logo_url": f"data:{mime};base64," + base64.b64encode(data).decode()}
    audit.admin_log(db, p.org.id, p.user, "org.logo_updated", p.org.slug, req=request); db.commit()
    return {"ok": True}


# ---------- audit log ----------
@router.get("/audit-log")
def admin_audit(format: str = "json", q: str | None = None, p: Principal = Depends(perm("envelopes.view_all")), db: Session = Depends(get_db)):
    qry = db.query(AdminAuditLog).filter_by(org_id=p.org.id)
    if q: qry = qry.filter(or_(AdminAuditLog.action.like(f"%{q}%"), AdminAuditLog.actor_email.like(f"%{q}%"), AdminAuditLog.target.like(f"%{q}%")))
    rows = qry.order_by(AdminAuditLog.id.desc()).limit(5000).all()
    if format == "csv":
        b = io.StringIO(); w = csv.writer(b); w.writerow(["utc_time", "actor", "action", "target", "ip", "before", "after"])
        for r in rows: w.writerow([r.created_at.isoformat() + "Z", r.actor_email, r.action, r.target, r.ip, json.dumps(r.before, default=str), json.dumps(r.after, default=str)])
        return Response(b.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="admin-audit-log.csv"'})
    return [{k: getattr(r, k) for k in ("id", "actor_email", "action", "target", "before", "after", "ip", "created_at")} for r in rows]


# ---------- contacts ----------
class ContactIn(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    company: str | None = None
    shared: bool = False


@router.get("/contacts")
def contacts(q: str | None = None, p: Principal = Depends(org_member), db: Session = Depends(get_db)):
    qry = db.query(Contact).filter(Contact.org_id == p.org.id, or_(Contact.owner_id == p.user.id, Contact.owner_id.is_(None)))
    if q: qry = qry.filter(or_(Contact.name.ilike(f"%{q}%"), Contact.email.ilike(f"%{q}%")))
    return [{"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "company": c.company, "shared": c.owner_id is None} for c in qry.order_by(Contact.name).limit(200)]


@router.post("/contacts", status_code=201)
def add_contact(body: ContactIn, p: Principal = Depends(org_member), db: Session = Depends(get_db)):
    c = Contact(org_id=p.org.id, owner_id=None if body.shared else p.user.id, name=body.name, email=str(body.email).lower(), phone=body.phone, company=body.company)
    db.add(c); db.commit()
    return {"id": c.id}


@router.delete("/contacts/{cid}")
def delete_contact(cid: int, p: Principal = Depends(org_member), db: Session = Depends(get_db)):
    c = db.get(Contact, cid)
    if not c or c.org_id != p.org.id or (c.owner_id not in (p.user.id, None)) or (c.owner_id is None and p.user.role != "org_admin"): raise HTTPException(404, "Contact not found")
    db.delete(c); db.commit()
    return {"deleted": True}


# ---------- outbox & notifications ----------
@router.get("/outbox")
def outbox(envelope_id: int | None = None, p: Principal = Depends(org_member), db: Session = Depends(get_db)):
    qry = db.query(EmailLog).filter(EmailLog.org_id == p.org.id)
    if p.user.role not in ("org_admin", "auditor"):
        own = [e.id for e in db.query(Envelope.id).filter_by(org_id=p.org.id, owner_id=p.user.id)]
        qry = qry.filter(or_(EmailLog.envelope_id.in_(own or [0]), EmailLog.to == p.user.email))
    if envelope_id: qry = qry.filter(EmailLog.envelope_id == envelope_id)
    rows = qry.order_by(EmailLog.id.desc()).limit(300).all()
    return {"smtp_configured": notify.smtp_configured(), "sms_configured": notify.sms_configured(),
            "messages": [{k: getattr(m, k) for k in ("id", "envelope_id", "channel", "to", "kind", "subject", "body", "link", "secret", "attachment", "delivery", "error", "created_at")} for m in rows]}


@router.get("/notifications")
def notifications(p: Principal = Depends(org_member), db: Session = Depends(get_db)):
    return [{"id": n.id, "text": n.text, "envelope_id": n.envelope_id, "read": n.read, "created_at": n.created_at}
            for n in db.query(Notification).filter_by(user_id=p.user.id).order_by(Notification.id.desc()).limit(50)]


@router.post("/notifications/read-all")
def read_all(p: Principal = Depends(org_member), db: Session = Depends(get_db)):
    db.query(Notification).filter_by(user_id=p.user.id, read=False).update({"read": True}); db.commit()
    return {"ok": True}
