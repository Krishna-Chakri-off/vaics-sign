"""Email (SMTP, e.g. Amazon SES) and SMS (provider adapters). Without a configured provider every message goes to the
DEV OUTBOX (EmailLog.delivery='dev_outbox') and is NOT delivered. Never report delivery that did not happen."""
import html, smtplib
from email.message import EmailMessage
from ..core.config import settings
from ..models import EmailLog, Notification, now
from . import i18n


def smtp_configured() -> bool:
    return bool(settings.SMTP_HOST)


def sms_configured() -> bool:
    return settings.SMS_PROVIDER == "twilio" and bool(settings.TWILIO_ACCOUNT_SID) or settings.SMS_PROVIDER == "msg91" and bool(settings.MSG91_AUTH_KEY)


def brand_of(org, envelope=None) -> dict:
    b = {"product_name": settings.BRAND_PRODUCT_NAME, "org_name": settings.BRAND_ORG_NAME, "primary": settings.BRAND_PRIMARY,
         "accent": settings.BRAND_ACCENT, "logo_url": settings.BRAND_LOGO_URL, "email_footer": "", "reply_to": ""}
    if org is not None:
        b["org_name"] = org.name
        b.update({k: v for k, v in (org.branding or {}).items() if v})
    if envelope is not None and envelope.brand:
        b.update({k: v for k, v in envelope.brand.items() if v})
    return b


def render_html(brand: dict, text_body: str, link: str | None, code: str | None, lang: str = "en") -> str:
    e = html.escape
    body = e(text_body).replace("\n", "<br>")
    btn = (f'<p style="margin:16px 0"><a href="{e(link)}" style="background:{e(brand["accent"])};color:#fff;padding:8px 12px;'
           f'text-decoration:none;font-weight:500;font-size:12px;display:inline-block">{e(i18n.t("email.open", lang))}</a></p>') if link else ""
    codeblock = f'<p style="font-size:24px;letter-spacing:6px;font-weight:600;color:{e(brand["primary"])};margin:16px 0">{e(code)}</p>' if code else ""
    footer = e(brand.get("email_footer") or "") or e(i18n.t("email.footer", lang, product=brand["product_name"]))
    return (f"<div style=\"font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:14px;color:#0F172A;max-width:600px;margin:auto\">"
            f'<div style="background:{e(brand["primary"])};color:#fff;padding:12px 16px;font-weight:600;font-size:14px">{e(brand["product_name"])} · {e(brand["org_name"])}</div>'
            f'<div style="border:1px solid #E5E7EB;border-top:3px solid {e(brand["accent"])};padding:16px;background:#fff">{body}{codeblock}{btn}</div>'
            f'<div style="color:#475569;font-size:12px;padding:8px 0">{footer}</div></div>')


def send_email(db, *, org, to: str, kind: str, subject: str, body: str, envelope=None, link: str | None = None,
               code: str | None = None, attachments: list[tuple[str, bytes]] | None = None, lang: str = "en") -> EmailLog:
    brand = brand_of(org, envelope)
    rec = EmailLog(org_id=org.id if org else None, envelope_id=envelope.id if envelope else None, channel="email", to=to, kind=kind,
                   subject=subject[:300], body=body, link=link, attachment=", ".join(a[0] for a in attachments or []) or None, delivery="dev_outbox")
    if not smtp_configured():
        rec.secret = code
        db.add(rec); db.flush(); return rec
    try:
        m = EmailMessage(); m["Subject"] = subject; m["From"] = f"{brand['product_name']} <{settings.SMTP_FROM}>"; m["To"] = to
        if brand.get("reply_to"): m["Reply-To"] = brand["reply_to"]
        txt = body + (f"\n\n{code}" if code else "") + (f"\n\n{link}" if link else "")
        m.set_content(txt)
        m.add_alternative(render_html(brand, body, link, code, lang), subtype="html")
        for name, data in attachments or []:
            m.add_attachment(data, maintype="application", subtype="pdf", filename=name)
        cls = smtplib.SMTP_SSL if settings.SMTP_SSL else smtplib.SMTP
        with cls(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as s:
            if not settings.SMTP_SSL: s.starttls()
            if settings.SMTP_USER: s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(m)
        rec.delivery = "accepted"  # accepted by the SMTP relay – not proof of inbox delivery
    except Exception as ex:  # noqa: BLE001
        rec.delivery, rec.error = "failed", str(ex)[:300]
    db.add(rec); db.flush(); return rec


def send_sms(db, *, org, to: str, kind: str, body: str, envelope=None, code: str | None = None) -> EmailLog:
    rec = EmailLog(org_id=org.id if org else None, envelope_id=envelope.id if envelope else None, channel="sms", to=to, kind=kind,
                   subject=f"SMS: {kind}", body=body, delivery="dev_outbox")
    if not sms_configured():
        rec.secret = code
        db.add(rec); db.flush(); return rec
    try:
        import httpx
        if settings.SMS_PROVIDER == "twilio":
            r = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json",
                           auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN), data={"To": to, "From": settings.TWILIO_FROM, "Body": body}, timeout=15)
        else:
            r = httpx.post("https://control.msg91.com/api/v5/flow/", headers={"authkey": settings.MSG91_AUTH_KEY},
                           json={"template_id": settings.MSG91_TEMPLATE_ID, "recipients": [{"mobiles": to.lstrip("+"), "otp": code or "", "body": body}]}, timeout=15)
        r.raise_for_status()
        rec.delivery, rec.provider_id = "accepted", str(r.json().get("sid") or r.json().get("request_id") or "")[:200]
    except Exception as ex:  # noqa: BLE001
        rec.delivery, rec.error = "failed", str(ex)[:300]
    db.add(rec); db.flush(); return rec


def notify_user(db, user_id: int, text: str, envelope_id: int | None = None):
    db.add(Notification(user_id=user_id, text=text[:300], envelope_id=envelope_id, created_at=now()))
