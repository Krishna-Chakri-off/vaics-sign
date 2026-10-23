"""Billing: plan catalogue pricing, invoices with tax, proration, and payment-provider adapters (Razorpay, Stripe).
Adapters call the providers' real REST APIs only when keys are configured; nothing is charged in this build unless an operator
configures live keys. Card data never touches VAICS Sign (hosted checkout / provider SDK)."""
import hashlib, hmac, json, time
from datetime import timedelta
from fastapi import HTTPException
from ..core.config import settings
from ..models import Invoice, Organization, Plan, now

GRACE_DAYS = 7
MAX_PAYMENT_RETRIES = 3


def price_minor(plan: Plan, currency: str, cycle: str) -> int:
    p = (plan.prices or {}).get(currency) or {}
    v = p.get(cycle)
    if v is None:
        raise HTTPException(422, f"Plan {plan.code} has no {cycle} price in {currency}")
    return int(round(float(v) * 100))


def tax_for(org: Organization, subtotal: int) -> dict:
    if org.country == "IN":
        if (org.billing_state_code or "") == settings.SELLER_STATE_CODE:
            half = round(subtotal * 0.09)
            return {"type": "CGST+SGST", "rate": 18, "cgst": half, "sgst": half, "amount": 2 * half, "seller_gstin": settings.SELLER_GSTIN or "NOT CONFIGURED"}
        amt = round(subtotal * 0.18)
        return {"type": "IGST", "rate": 18, "amount": amt, "seller_gstin": settings.SELLER_GSTIN or "NOT CONFIGURED"}
    if org.country in EU_UK:
        if org.tax_id:
            return {"type": "VAT reverse charge", "rate": 0, "amount": 0, "note": "Reverse charge – customer to account for VAT"}
        return {"type": "VAT", "rate": None, "amount": 0, "note": "VAT rate for B2C/without VAT ID is not configured – invoice requires review"}
    return {"type": "none", "rate": 0, "amount": 0, "note": "Sales tax not calculated – requires a tax engine (e.g. Stripe Tax) before production"}


EU_UK = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "GB"}


def next_invoice_number(db) -> str:
    n = db.query(Invoice).count() + 1
    return f"VS-{now():%Y%m}-{n:05d}"


def create_invoice(db, org: Organization, lines: list[dict], period_days: int | None = None) -> Invoice:
    subtotal = sum(int(l["amount"]) for l in lines)
    tax = tax_for(org, subtotal)
    inv = Invoice(org_id=org.id, number=next_invoice_number(db), currency=org.currency, lines=lines, subtotal=subtotal, tax=tax,
                  total=subtotal + int(tax.get("amount") or 0), customer_tax_id=org.tax_id, po_reference=org.po_reference,
                  period_start=now(), period_end=now() + timedelta(days=period_days) if period_days else None)
    db.add(inv); db.flush(); return inv


def subscription_lines(plan: Plan, org: Organization, cycle: str, seats: int) -> list[dict]:
    unit = price_minor(plan, org.currency, cycle)
    return [{"description": f"{plan.name} plan – {cycle} – {seats} seat(s)", "quantity": seats, "unit": unit, "amount": unit * seats}]


def prorated_seat_line(plan: Plan, org: Organization, delta: int) -> dict:
    unit = price_minor(plan, org.currency, org.billing_cycle)
    if not org.current_period_end:
        return {"description": f"{delta} seat(s)", "quantity": delta, "unit": unit, "amount": unit * delta}
    total_days = 365 if org.billing_cycle == "annual" else 30
    remaining = max(0, (org.current_period_end - now()).days)
    amt = round(unit * delta * remaining / total_days)
    return {"description": f"{'Add' if delta > 0 else 'Remove'} {abs(delta)} seat(s), prorated {remaining}/{total_days} days", "quantity": delta, "unit": unit, "amount": amt}


def activate(db, org: Organization, plan: Plan, cycle: str, seats: int):
    org.plan_id, org.billing_cycle, org.seats, org.status = plan.id, cycle, seats, "active"
    org.current_period_end = now() + timedelta(days=365 if cycle == "annual" else 30)
    org.grace_until = None


def mark_paid(db, inv: Invoice, provider_ref: str | None = None):
    inv.status, inv.paid_at, inv.provider_ref = "paid", now(), provider_ref or inv.provider_ref
    org = db.get(Organization, inv.org_id)
    pending = (inv.lines[0] or {}).get("activate") if inv.lines else None
    if pending:
        plan = db.query(Plan).filter_by(code=pending["plan"]).first()
        activate(db, org, plan, pending["cycle"], pending["seats"])
    elif org.status in ("past_due", "restricted"):
        org.status, org.grace_until = "active", None


def mark_failed(db, inv: Invoice, reason: str = ""):
    inv.attempts += 1
    inv.status = "failed" if inv.attempts >= MAX_PAYMENT_RETRIES else "open"
    org = db.get(Organization, inv.org_id)
    if org.status == "active":
        org.status, org.grace_until = "past_due", now() + timedelta(days=GRACE_DAYS)


# ---------------- provider adapters ----------------
class Provider:
    code = "none"

    def configured(self) -> bool:
        return False

    def checkout(self, inv: Invoice, org: Organization) -> dict:
        raise HTTPException(503, f"Payment provider '{self.code}' is not configured on this server. No payment was taken.")

    def verify_webhook(self, body: bytes, headers) -> dict:
        raise HTTPException(400, "Webhook verification not configured")


class Razorpay(Provider):
    code = "razorpay"

    def configured(self):
        return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)

    def checkout(self, inv, org):
        if not self.configured():
            return super().checkout(inv, org)
        import httpx
        r = httpx.post("https://api.razorpay.com/v1/orders", auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
                       json={"amount": inv.total, "currency": inv.currency, "receipt": inv.number, "notes": {"invoice": inv.number}}, timeout=20)
        if r.status_code >= 300:
            raise HTTPException(502, f"Razorpay error: {r.text[:200]}")
        inv.provider, inv.provider_ref = "razorpay", r.json()["id"]
        return {"provider": "razorpay", "order_id": inv.provider_ref, "key_id": settings.RAZORPAY_KEY_ID, "amount": inv.total, "currency": inv.currency}

    def verify_webhook(self, body, headers):
        if not settings.RAZORPAY_WEBHOOK_SECRET:
            return super().verify_webhook(body, headers)
        sig = headers.get("x-razorpay-signature", "")
        exp = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, exp):
            raise HTTPException(400, "Invalid Razorpay signature")
        ev = json.loads(body)
        ent = (ev.get("payload", {}).get("payment", {}) or {}).get("entity", {})
        return {"type": {"payment.captured": "paid", "order.paid": "paid", "payment.failed": "failed"}.get(ev.get("event"), "ignored"),
                "receipt": (ent.get("notes") or {}).get("invoice"), "order_id": ent.get("order_id"), "ref": ent.get("id")}


class Stripe(Provider):
    code = "stripe"

    def configured(self):
        return bool(settings.STRIPE_SECRET_KEY)

    def checkout(self, inv, org):
        if not self.configured():
            return super().checkout(inv, org)
        import httpx
        r = httpx.post("https://api.stripe.com/v1/checkout/sessions", auth=(settings.STRIPE_SECRET_KEY, ""), timeout=20, data={
            "mode": "payment", "success_url": f"{settings.PUBLIC_APP_URL}/admin/billing?paid=1", "cancel_url": f"{settings.PUBLIC_APP_URL}/admin/billing",
            "client_reference_id": inv.number, "metadata[invoice]": inv.number,
            "line_items[0][price_data][currency]": inv.currency.lower(), "line_items[0][price_data][unit_amount]": inv.total,
            "line_items[0][price_data][product_data][name]": f"VAICS Sign invoice {inv.number}", "line_items[0][quantity]": 1})
        if r.status_code >= 300:
            raise HTTPException(502, f"Stripe error: {r.text[:200]}")
        inv.provider, inv.provider_ref = "stripe", r.json()["id"]
        return {"provider": "stripe", "checkout_url": r.json()["url"]}

    def verify_webhook(self, body, headers, tolerance=300):
        if not settings.STRIPE_WEBHOOK_SECRET:
            return super().verify_webhook(body, headers)
        parts = dict(p.split("=", 1) for p in headers.get("stripe-signature", "").split(",") if "=" in p)
        ts = parts.get("t", "0")
        exp = hmac.new(settings.STRIPE_WEBHOOK_SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(parts.get("v1", ""), exp) or abs(time.time() - int(ts)) > tolerance:
            raise HTTPException(400, "Invalid Stripe signature")
        ev = json.loads(body); obj = ev.get("data", {}).get("object", {})
        return {"type": {"checkout.session.completed": "paid", "payment_intent.payment_failed": "failed"}.get(ev.get("type"), "ignored"),
                "receipt": (obj.get("metadata") or {}).get("invoice") or obj.get("client_reference_id"), "ref": obj.get("id")}


PROVIDERS = {"razorpay": Razorpay(), "stripe": Stripe()}


def provider_for(org: Organization) -> Provider:
    return PROVIDERS.get(settings.BILLING_PROVIDER_IN if org.country == "IN" else settings.BILLING_PROVIDER_INTL, Provider())


def invoice_pdf(inv: Invoice, org: Organization) -> bytes:
    import io
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor
    from .pdfstamp import _fonts
    _fonts()
    b = io.BytesIO(); c = canvas.Canvas(b, pagesize=A4); W, H = A4
    c.setFillColor(HexColor("#0D47A1")); c.rect(0, H - 56, W, 56, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF")); c.setFont("VSSans-Bold", 14); c.drawString(36, H - 34, "TAX INVOICE" if org.country == "IN" else "INVOICE")
    c.setFillColor(HexColor("#0F172A")); c.setFont("VSSans", 9); y = H - 80
    m = lambda v: f"{inv.currency} {v / 100:,.2f}"
    for t in [f"Invoice: {inv.number}    Date: {inv.created_at:%d %b %Y}    Status: {inv.status}", f"Supplier: VAICS Consulting, Hyderabad, India    GSTIN: {settings.SELLER_GSTIN or 'NOT CONFIGURED'}",
              f"Customer: {org.name}    Tax ID: {org.tax_id or '-'}    PO: {org.po_reference or '-'}", f"Address: {org.billing_address or '-'}", ""]:
        c.drawString(36, y, t); y -= 14
    for l in inv.lines:
        c.drawString(36, y, l["description"][:80]); c.drawRightString(W - 36, y, m(l["amount"])); y -= 14
    y -= 6; c.drawString(300, y, "Subtotal"); c.drawRightString(W - 36, y, m(inv.subtotal)); y -= 14
    tx = inv.tax or {}
    c.drawString(300, y, f"{tx.get('type')} {tx.get('rate') if tx.get('rate') is not None else ''}%"); c.drawRightString(W - 36, y, m(int(tx.get("amount") or 0))); y -= 14
    c.setFont("VSSans-Bold", 10); c.drawString(300, y, "Total"); c.drawRightString(W - 36, y, m(inv.total)); y -= 24
    c.setFont("VSSans", 7); c.setFillColor(HexColor("#475569"))
    if tx.get("note"): c.drawString(36, y, tx["note"]); y -= 10
    c.drawString(36, y, "Generated by VAICS Sign. Tax treatment must be reviewed by a qualified accountant before production use (HSN/SAC 998314).")
    c.save(); return b.getvalue()
