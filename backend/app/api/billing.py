from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field as PField
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..models import Plan, Invoice, Credit, Organization, Coupon, User, now
from ..services import billing as bl, audit, usage
from .deps import Principal, perm, org_member

router = APIRouter(prefix="/billing", tags=["billing"])


def plan_out(p: Plan):
    return {k: getattr(p, k) for k in ("id", "code", "name", "description", "features", "limits", "prices", "is_public", "is_custom", "active")}


def inv_out(i: Invoice):
    return {k: getattr(i, k) for k in ("id", "number", "status", "currency", "lines", "subtotal", "tax", "total", "customer_tax_id", "po_reference", "provider", "provider_ref", "attempts", "paid_at", "created_at")}


@router.get("/plans")
def plans(db: Session = Depends(get_db)):
    return [plan_out(p) for p in db.query(Plan).filter_by(is_public=True, active=True).order_by(Plan.id)]


@router.get("/subscription")
def subscription(p: Principal = Depends(org_member), db: Session = Depends(get_db)):
    o = p.org
    return {"status": o.status, "plan": plan_out(o.plan) if o.plan else None, "cycle": o.billing_cycle, "seats": o.seats, "currency": o.currency,
            "trial_ends_at": o.trial_ends_at, "current_period_end": o.current_period_end, "grace_until": o.grace_until, "usage": usage.summary(db, o),
            "provider": bl.provider_for(o).code, "provider_configured": bl.provider_for(o).configured()}


class CheckoutIn(BaseModel):
    plan: str
    cycle: str = PField("monthly", pattern="^(monthly|annual)$")
    seats: int = PField(1, ge=1, le=10000)
    coupon: str | None = None


@router.post("/checkout")
def checkout(body: CheckoutIn, request: Request, p: Principal = Depends(perm("billing.manage")), db: Session = Depends(get_db)):
    plan = db.query(Plan).filter_by(code=body.plan, active=True).first()
    if not plan or (not plan.is_public and not plan.is_custom): raise HTTPException(404, "Plan not found")
    active = db.query(User).filter_by(org_id=p.org.id, is_active=True).count()
    if body.seats < active: raise HTTPException(422, f"You have {active} active users; choose at least {active} seats")
    lines = bl.subscription_lines(plan, p.org, body.cycle, body.seats)
    if body.coupon:
        c = db.query(Coupon).filter_by(code=body.coupon.upper(), active=True).first()
        if not c or (c.expires_at and c.expires_at < now()): raise HTTPException(422, "Invalid coupon")
        disc = -round(sum(l["amount"] for l in lines) * c.percent_off / 100)
        lines.append({"description": f"Coupon {c.code} ({c.percent_off}% off)", "quantity": 1, "unit": disc, "amount": disc})
    lines[0]["activate"] = {"plan": plan.code, "cycle": body.cycle, "seats": body.seats}
    inv = bl.create_invoice(db, p.org, lines, 365 if body.cycle == "annual" else 30)
    if inv.total == 0:
        bl.mark_paid(db, inv, "free")
        audit.admin_log(db, p.org.id, p.user, "billing.plan_changed", plan.code, after={"cycle": body.cycle, "seats": body.seats}, req=request); db.commit()
        return {"invoice": inv_out(inv), "paid": True}
    prov = bl.provider_for(p.org)
    try:
        session = prov.checkout(inv, p.org)
    except HTTPException:
        db.commit()  # keep the open invoice for reference
        raise
    audit.admin_log(db, p.org.id, p.user, "billing.checkout_started", plan.code, after={"invoice": inv.number, "provider": prov.code}, req=request); db.commit()
    return {"invoice": inv_out(inv), "checkout": session}


class SeatsIn(BaseModel):
    seats: int = PField(ge=1, le=10000)


@router.post("/seats")
def change_seats(body: SeatsIn, request: Request, p: Principal = Depends(perm("billing.manage")), db: Session = Depends(get_db)):
    o = p.org
    active = db.query(User).filter_by(org_id=o.id, is_active=True).count()
    if body.seats < active: raise HTTPException(422, f"{active} users are active; deactivate users before removing seats")
    delta = body.seats - o.seats
    if delta == 0: return {"seats": o.seats}
    inv = None
    if o.plan and o.status == "active":
        line = bl.prorated_seat_line(o.plan, o, delta)
        if line["amount"] > 0:
            line["activate"] = None
            inv = bl.create_invoice(db, o, [line])
    before = o.seats; o.seats = body.seats
    audit.admin_log(db, o.id, p.user, "billing.seats_changed", str(body.seats), before={"seats": before}, after={"seats": body.seats, "invoice": inv.number if inv else None}, req=request)
    db.commit()
    return {"seats": o.seats, "invoice": inv_out(inv) if inv else None, "note": "Seat reductions are credited at renewal (no refund issued automatically)." if delta < 0 else None}


class CreditsIn(BaseModel):
    metric: str = PField(pattern="^(envelopes|sms|aadhaar|dsc|idv)$")
    quantity: int = PField(ge=1, le=100000)


CREDIT_PRICE = {"INR": {"envelopes": 50, "sms": 2, "aadhaar": 30, "dsc": 30, "idv": 100}, "USD": {"envelopes": 1, "sms": 0.05, "aadhaar": 0.5, "dsc": 0.5, "idv": 2}, "EUR": {"envelopes": 1, "sms": 0.05, "aadhaar": 0.5, "dsc": 0.5, "idv": 2}}


@router.post("/credits")
def buy_credits(body: CreditsIn, request: Request, p: Principal = Depends(perm("billing.manage")), db: Session = Depends(get_db)):
    usage.require_feature(p.org, "top_ups", "Credit top-ups")
    unit = round(CREDIT_PRICE.get(p.org.currency, CREDIT_PRICE["USD"])[body.metric] * 100)
    inv = bl.create_invoice(db, p.org, [{"description": f"{body.quantity} {body.metric} credits", "quantity": body.quantity, "unit": unit, "amount": unit * body.quantity,
                                         "credit": {"metric": body.metric, "quantity": body.quantity}}])
    prov = bl.provider_for(p.org)
    try:
        session = prov.checkout(inv, p.org)
    except HTTPException:
        db.commit(); raise
    db.commit()
    return {"invoice": inv_out(inv), "checkout": session}


@router.post("/cancel")
def cancel(request: Request, p: Principal = Depends(perm("billing.manage")), db: Session = Depends(get_db)):
    free = db.query(Plan).filter_by(code="free").first()
    before = p.org.plan.code if p.org.plan else None
    p.org.plan_id, p.org.status, p.org.current_period_end = free.id, "active", None
    audit.admin_log(db, p.org.id, p.user, "billing.cancelled", before or "", after={"plan": "free"}, req=request); db.commit()
    return {"plan": "free", "note": "Downgraded to Free. Data is kept; paid features are disabled."}


@router.get("/invoices")
def invoices(p: Principal = Depends(perm("billing.manage")), db: Session = Depends(get_db)):
    return [inv_out(i) for i in db.query(Invoice).filter_by(org_id=p.org.id).order_by(Invoice.id.desc())]


@router.get("/invoices/{iid}/pdf")
def invoice_pdf(iid: int, p: Principal = Depends(perm("billing.manage")), db: Session = Depends(get_db)):
    i = db.get(Invoice, iid)
    if not i or i.org_id != p.org.id: raise HTTPException(404, "Invoice not found")
    return Response(bl.invoice_pdf(i, p.org), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{i.number}.pdf"'})


@router.get("/usage-statement")
def usage_statement(p: Principal = Depends(perm("billing.manage")), db: Session = Depends(get_db)):
    from sqlalchemy import func
    from ..models import UsageRecord
    rows = db.query(UsageRecord.period, UsageRecord.metric, func.sum(UsageRecord.quantity)).filter_by(org_id=p.org.id).group_by(UsageRecord.period, UsageRecord.metric).all()
    return [{"period": a, "metric": b, "quantity": int(c)} for a, b, c in sorted(rows)]


def _apply_event(db, ev: dict):
    if ev["type"] == "ignored" or not ev.get("receipt"): return {"handled": False}
    inv = db.query(Invoice).filter_by(number=ev["receipt"]).first()
    if not inv: return {"handled": False}
    if ev["type"] == "paid" and inv.status != "paid":
        bl.mark_paid(db, inv, ev.get("ref"))
        for l in inv.lines:
            if l.get("credit"): db.add(Credit(org_id=inv.org_id, metric=l["credit"]["metric"], quantity=l["credit"]["quantity"], reference=inv.number))
    elif ev["type"] == "failed":
        bl.mark_failed(db, inv)
    audit.admin_log(db, inv.org_id, "payment-provider", f"billing.payment_{ev['type']}", inv.number, after={"ref": ev.get("ref")})
    db.commit()
    return {"handled": True}


@router.post("/webhooks/razorpay", include_in_schema=False)
async def razorpay_hook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    return _apply_event(db, bl.PROVIDERS["razorpay"].verify_webhook(body, request.headers))


@router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_hook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    return _apply_event(db, bl.PROVIDERS["stripe"].verify_webhook(body, request.headers))
