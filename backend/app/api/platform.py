"""Platform Admin console (VAICS operations). No access to document content; envelope metadata only during customer-granted support access."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..core.config import settings
from ..core.db import get_db, engine
from ..models import Organization, Plan, User, Envelope, Coupon, Invoice, AdminAuditLog, now
from ..services import audit, notify, seal, trust, billing as bl, usage
from ..services.storage import storage
from .deps import Principal, platform_admin
from .billing import plan_out

router = APIRouter(prefix="/platform", tags=["platform admin"])


@router.get("/tenants")
def tenants(q: str | None = None, p: Principal = Depends(platform_admin), db: Session = Depends(get_db)):
    qry = db.query(Organization)
    if q: qry = qry.filter(Organization.name.ilike(f"%{q}%"))
    out = []
    for o in qry.order_by(Organization.id.desc()).limit(500):
        out.append({"id": o.id, "name": o.name, "slug": o.slug, "country": o.country, "region": o.region, "status": o.status, "plan": o.plan.code if o.plan else None,
                    "seats": o.seats, "users": db.query(User).filter_by(org_id=o.id).count(), "envelopes": db.query(Envelope).filter_by(org_id=o.id).count(),
                    "trial_ends_at": o.trial_ends_at, "created_at": o.created_at, "is_sandbox": o.is_sandbox, "support_access_until": o.support_access_until})
    return out


class StatusIn(BaseModel):
    status: str
    reason: str = ""


@router.post("/tenants/{oid}/status")
def set_status(oid: int, body: StatusIn, request: Request, p: Principal = Depends(platform_admin), db: Session = Depends(get_db)):
    o = db.get(Organization, oid)
    if not o: raise HTTPException(404, "Tenant not found")
    if body.status not in ("active", "suspended", "restricted", "closed"): raise HTTPException(422, "Invalid status")
    before = o.status
    o.status, o.suspended_reason = body.status, body.reason or None
    if body.status == "closed": o.closed_at = now()
    audit.admin_log(db, o.id, p.user, f"platform.tenant_{body.status}", o.slug, before={"status": before}, after={"status": o.status, "reason": body.reason}, req=request)
    db.commit()
    return {"status": o.status}


class AssignIn(BaseModel):
    plan: str
    seats: int | None = None
    trial_days: int | None = None
    po_reference: str | None = None


@router.post("/tenants/{oid}/plan")
def assign_plan(oid: int, body: AssignIn, request: Request, p: Principal = Depends(platform_admin), db: Session = Depends(get_db)):
    """Enterprise contracts / invoice billing (FR-019): assign plan directly; billing by invoice outside online checkout."""
    o = db.get(Organization, oid); plan = db.query(Plan).filter_by(code=body.plan).first()
    if not o or not plan: raise HTTPException(404, "Not found")
    before = {"plan": o.plan.code if o.plan else None, "seats": o.seats}
    if body.trial_days:
        o.plan_id, o.status, o.trial_ends_at, o.trial_reminded = plan.id, "trial", now() + timedelta(days=body.trial_days), False
    else:
        bl.activate(db, o, plan, o.billing_cycle, body.seats or o.seats)
    if body.po_reference: o.po_reference = body.po_reference
    audit.admin_log(db, o.id, p.user, "platform.plan_assigned", o.slug, before=before, after={"plan": plan.code, "seats": o.seats, "trial_days": body.trial_days}, req=request)
    db.commit()
    return {"plan": plan.code, "status": o.status}


@router.get("/tenants/{oid}/envelopes")
def support_envelopes(oid: int, request: Request, p: Principal = Depends(platform_admin), db: Session = Depends(get_db)):
    o = db.get(Organization, oid)
    if not o: raise HTTPException(404, "Tenant not found")
    if not o.support_access_until or o.support_access_until < now():
        raise HTTPException(403, "The customer has not granted support access")
    audit.admin_log(db, o.id, p.user, "platform.support_viewed_envelopes", o.slug, req=request); db.commit()
    return [{"public_id": e.public_id, "status": e.status, "created_at": e.created_at, "recipients": len(e.recipients)} for e in db.query(Envelope).filter_by(org_id=o.id).limit(200)]


class PlanIn(BaseModel):
    code: str
    name: str
    description: str = ""
    features: dict = {}
    limits: dict = {}
    prices: dict = {}
    is_public: bool = True
    is_custom: bool = False
    active: bool = True


@router.get("/plans")
def all_plans(p: Principal = Depends(platform_admin), db: Session = Depends(get_db)):
    return [plan_out(x) for x in db.query(Plan).order_by(Plan.id)]


@router.post("/plans", status_code=201)
def create_plan(body: PlanIn, request: Request, p: Principal = Depends(platform_admin), db: Session = Depends(get_db)):
    if db.query(Plan).filter_by(code=body.code).first(): raise HTTPException(409, "Plan code exists")
    x = Plan(**body.model_dump()); db.add(x)
    audit.admin_log(db, None, p.user, "platform.plan_created", body.code, after=body.model_dump(), req=request); db.commit()
    return plan_out(x)


@router.put("/plans/{code}")
def update_plan(code: str, body: PlanIn, request: Request, p: Principal = Depends(platform_admin), db: Session = Depends(get_db)):
    x = db.query(Plan).filter_by(code=code).first()
    if not x: raise HTTPException(404, "Plan not found")
    before = plan_out(x)
    for k, v in body.model_dump().items():
        if k != "code": setattr(x, k, v)
    audit.admin_log(db, None, p.user, "platform.plan_updated", code, before=before, after=body.model_dump(), req=request); db.commit()
    return plan_out(x)


class CouponIn(BaseModel):
    code: str
    percent_off: int


@router.post("/coupons", status_code=201)
def coupon(body: CouponIn, request: Request, p: Principal = Depends(platform_admin), db: Session = Depends(get_db)):
    c = Coupon(code=body.code.upper(), percent_off=max(0, min(100, body.percent_off))); db.add(c)
    audit.admin_log(db, None, p.user, "platform.coupon_created", c.code, after={"percent_off": c.percent_off}, req=request); db.commit()
    return {"code": c.code}


@router.get("/health")
def health(p: Principal = Depends(platform_admin), db: Session = Depends(get_db)):
    db_ok = True
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception:
        db_ok = False
    return {"database": "ok" if db_ok else "error", "dialect": engine.dialect.name, "storage": storage().name, "email": "smtp" if notify.smtp_configured() else "dev_outbox",
            "sms": settings.SMS_PROVIDER if notify.sms_configured() else "dev_outbox", "seal": seal.seal_mode(), "signature_providers": trust.status(),
            "payment_providers": {k: v.configured() for k, v in bl.PROVIDERS.items()}, "malware_scan": "clamd" if settings.CLAMD_HOST else "not configured",
            "tenants": db.query(Organization).count(), "users": db.query(User).count(), "envelopes": db.query(Envelope).count(),
            "envelopes_this_month": db.query(Envelope).filter(Envelope.sent_at >= now().replace(day=1, hour=0, minute=0, second=0)).count()}


@router.get("/audit-log")
def platform_log(p: Principal = Depends(platform_admin), db: Session = Depends(get_db)):
    return [{k: getattr(r, k) for k in ("id", "org_id", "actor_email", "action", "target", "after", "ip", "created_at")}
            for r in db.query(AdminAuditLog).filter(AdminAuditLog.action.like("platform.%")).order_by(AdminAuditLog.id.desc()).limit(500)]


@router.get("/subprocessors", tags=["public"])
def subprocessors():
    return SUBPROCESSORS


SUBPROCESSORS = [
    {"name": "Amazon Web Services", "purpose": "Hosting, storage, email (SES)", "regions": ["ap-south-1 Mumbai", "eu-central-1 Frankfurt", "us-east-1 N. Virginia"]},
    {"name": "Razorpay", "purpose": "Payments (India)", "regions": ["India"]},
    {"name": "Stripe", "purpose": "Payments (international)", "regions": ["US", "EU"]},
    {"name": "SMS provider (Twilio / MSG91)", "purpose": "SMS OTP", "regions": ["per provider"]},
]
