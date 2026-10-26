"""Stamping signatures/field values onto PDFs at exact positions (handles /Rotate and CropBox) and building the Certificate of Completion."""
import base64, io, os
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
SIG_FONTS = {"great_vibes": "GreatVibes-Regular.ttf", "allura": "Allura-Regular.ttf", "sacramento": "Sacramento-Regular.ttf"}
_registered = False


def _fonts():
    global _registered
    if _registered:
        return
    for name, f in SIG_FONTS.items():
        pdfmetrics.registerFont(TTFont(f"sig_{name}", os.path.join(ASSETS, f)))
    pdfmetrics.registerFont(TTFont("VSSans", os.path.join(ASSETS, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("VSSans-Bold", os.path.join(ASSETS, "DejaVuSans-Bold.ttf")))
    _registered = True


def fmt_times(ts, tz: str = "Asia/Kolkata"):
    u = ts.replace(tzinfo=timezone.utc)
    try:
        z = ZoneInfo(tz)
    except Exception:
        z = ZoneInfo("Asia/Kolkata")
    loc = u.astimezone(z)
    off = loc.strftime("%z"); off = f"{off[:3]}:{off[3:]}" if off else "+00:00"
    return f"{loc:%d %b %Y %H:%M:%S} {loc.tzname()} (UTC{off})", u.strftime("%Y-%m-%d %H:%M:%S UTC")


def _fit(text, font, size, width, min_size=2.5):
    while size > min_size and pdfmetrics.stringWidth(text, font, size) > width:
        size -= 0.25
    return size


def page_matrix(page):
    """Transformation from displayed (rotated, cropbox-relative, bottom-left origin) space to the page's user space."""
    cb = page.cropbox
    ox, oy, cw, ch = float(cb.left), float(cb.bottom), float(cb.width), float(cb.height)
    rot = int(page.get("/Rotate", 0) or 0) % 360
    m = {0: (1, 0, 0, 1, 0, 0), 90: (0, 1, -1, 0, cw, 0), 180: (-1, 0, 0, -1, cw, ch), 270: (0, -1, 1, 0, 0, ch)}[rot]
    a, b, c, d, e, f = m
    return Transformation((a, b, c, d, e + ox, f + oy)), (ch, cw) if rot in (90, 270) else (cw, ch)


def draw_signature(c, r, x, y, w, h, initials=False, color="#0D47A1"):
    """Draw the recipient's adopted signature (typed/drawn/uploaded) inside the box (bottom-left x,y)."""
    _fonts()
    if r.signature_kind in ("drawn", "uploaded") and r.signature_image and "," in r.signature_image:
        img = ImageReader(io.BytesIO(base64.b64decode(r.signature_image.split(",", 1)[1])))
        c.drawImage(img, x, y, width=w, height=h, mask="auto", preserveAspectRatio=True, anchor="w")  # keep proportions; never stretch
        return
    font = f"sig_{r.signature_style if r.signature_style in SIG_FONTS else 'great_vibes'}"
    text = (r.initials or "".join(p[0] for p in r.name.split() if p).upper()) if initials else r.name
    size = _fit(text, font, min(h * 0.72, 44), w - 4, 6)  # script fonts: ~0.3em descender, keep clear of the text below
    c.setFillColor(HexColor(color)); c.setFont(font, size); c.drawString(x + 2, y + size * 0.3 + 1, text)


def stamp_document(src: bytes, fields, recipients: dict, tz: str, brand: dict) -> bytes:
    _fonts()
    reader = PdfReader(io.BytesIO(src)); writer = PdfWriter()
    blue, muted, ink = HexColor(brand["primary"]), HexColor("#475569"), HexColor("#0F172A")
    for i, page in enumerate(reader.pages, start=1):
        tm, (W, H) = page_matrix(page)
        pf = [f for f in fields if f.page == i and (f.value not in (None, "") or f.signed_at)]
        if not pf:
            writer.add_page(page); continue
        buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=(W, H))
        for f in pf:
            r = recipients[f.recipient_id]
            bx, by, bw, bh = f.x * W, H - (f.y + f.h) * H, f.w * W, f.h * H
            if f.type == "signature":
                c.setStrokeColor(blue); c.setLineWidth(0.6); c.rect(bx, by, bw, bh)
                loc, utc = fmt_times(f.signed_at, tz)
                lines = [(f"Name: {r.name}", "VSSans-Bold")]
                if f.reason: lines.append((f"Reason: {f.reason}", "VSSans"))
                lines += [(loc, "VSSans"), (utc, "VSSans"), (f"SHA-256: {f.field_hash}", "VSSans")]
                small = max(3.0, min(6.5, bh / (len(lines) + 4)))
                text_h = small * 1.22 * len(lines) + 2
                draw_signature(c, r, bx + 1, by + text_h, bw - 2, max(6, bh - text_h - 1), color=brand["primary"])
                yy = by + 2 + small * 1.22 * (len(lines) - 1)
                for txt, font in lines:
                    c.setFillColor(ink if font.endswith("Bold") else muted); c.setFont(font, _fit(txt, font, small, bw - 4)); c.drawString(bx + 2, yy, txt); yy -= small * 1.22
            elif f.type == "initials":
                draw_signature(c, r, bx, by, bw, bh, initials=True, color=brand["primary"])
            elif f.type == "checkbox":
                c.setStrokeColor(ink); s = min(bw, bh); c.rect(bx, by + bh - s, s, s)
                if f.value in ("true", "1", "X", "on", "yes"):
                    c.setFont("VSSans-Bold", s * 0.9); c.setFillColor(ink); c.drawString(bx + s * 0.15, by + bh - s * 0.85, "✓")
            elif f.type == "stamp":
                c.setStrokeColor(HexColor(brand["accent"])); c.setLineWidth(1.2); c.rect(bx, by, bw, bh)
                c.setFillColor(HexColor(brand["accent"])); txt = f.value or brand["org_name"]; c.setFont("VSSans-Bold", _fit(txt, "VSSans-Bold", min(bh * 0.4, 12), bw - 4)); c.drawCentredString(bx + bw / 2, by + bh / 2 - 3, txt)
            elif f.type == "attachment":
                txt = f"Attachment: {f.value}"; c.setFillColor(muted); c.setFont("VSSans", _fit(txt, "VSSans", f.font_size or 9, bw - 2)); c.drawString(bx + 1, by + 2, txt)
            else:
                txt = str(f.value); size = _fit(txt, "VSSans", min(f.font_size or 10, bh * 0.8), bw - 2)
                c.setFillColor(ink); c.setFont("VSSans", size); c.drawString(bx + 1, by + max(1, (bh - size) / 2), txt)
        c.save(); buf.seek(0)
        page.merge_transformed_page(PdfReader(buf).pages[0], tm)
        writer.add_page(page)
    out = io.BytesIO(); writer.write(out); return out.getvalue()


def certificate(env, docs, recipients, fields, events, owner, brand: dict, tz: str, sealed_note: str) -> bytes:
    _fonts()
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); W, H = A4
    blue, accent, ink, muted = HexColor(brand["primary"]), HexColor(brand["accent"]), HexColor("#0F172A"), HexColor("#475569")
    state = {"y": 0}

    def header():
        c.setFillColor(blue); c.rect(0, H - 58, W, 58, fill=1, stroke=0)
        c.setFillColor(accent); c.rect(0, H - 61, W, 3, fill=1, stroke=0)
        c.setFillColor(HexColor("#FFFFFF")); c.setFont("VSSans-Bold", 14); c.drawString(36, H - 36, f"{brand['product_name']} — Certificate of Completion")
        c.setFont("VSSans", 8); c.drawRightString(W - 36, H - 36, brand["org_name"])
        state["y"] = H - 86

    def need(hh):
        if state["y"] - hh < 40:
            c.showPage(); header()

    def line(t, f="VSSans", s=8.5, col=ink, indent=0):
        need(s + 4); c.setFillColor(col); c.setFont(f, _fit(t, f, s, W - 72 - indent)); c.drawString(36 + indent, state["y"], t); state["y"] -= s + 4

    header()
    line(env.title, "VSSans-Bold", 12)
    line(f"Envelope ID: {env.public_id}    Status: {env.status}    Organization: {brand['org_name']}")
    line(f"Sender: {owner.full_name} <{owner.email}>    Sent: {fmt_times(env.sent_at, tz)[1] if env.sent_at else '-'}    Completed: {fmt_times(env.completed_at, tz)[1] if env.completed_at else '-'}")
    line(f"Final document version hash: {env.version_hash}", s=7)
    state["y"] -= 4; line("Documents", "VSSans-Bold", 10)
    for d in docs:
        line(f"{d.order}. {d.name} — {len(d.pages)} page(s) — original SHA-256 {d.sha256}", s=7.5, indent=8)
        if d.source_sha256 and d.source_sha256 != d.sha256:
            line(f"uploaded as {d.source_name} (SHA-256 {d.source_sha256}), converted to PDF", s=7, col=muted, indent=18)
    state["y"] -= 4; line("Recipients", "VSSans-Bold", 10)
    for r in sorted(recipients, key=lambda r: (r.order, r.id)):
        need(70)
        line(f"Step {r.order} · {r.type} · {r.name} <{r.email}>{' · ' + r.role_name if r.role_name else ''}", "VSSans-Bold", 8.5, indent=8)
        auth = {"none": "email link only", "access_code": "link + separately delivered access code", "email_otp": "link + email one-time code", "sms_otp": "link + SMS one-time code"}.get(r.auth_method, r.auth_method)
        if r.type == "in_person": auth = f"in-person, hosted (host verified ID: {r.id_verification.get('id_type', '-')} {r.id_verification.get('id_last4', '')})"
        line(f"Authentication: {auth}    Signature type: {r.signature_type}    Status: {r.status}", s=7.5, col=muted, indent=18)
        if r.completed_at:
            loc, utc = fmt_times(r.completed_at, tz)
            line(f"Completed: {loc} | {utc}    IP: {r.completed_ip or '-'}", s=7.5, col=muted, indent=18)
            line(f"Consent to electronic records: {fmt_times(r.consent_at, tz)[1] if r.consent_at else '-'}    Device: {(r.completed_ua or '-')[:90]}", s=7, col=muted, indent=18)
        if r.decline_reason:
            line(f"Declined: {r.decline_reason}", s=7.5, col=HexColor("#B91C1C"), indent=18)
        rf = [f for f in fields if f.recipient_id == r.id and f.type == "signature" and f.signed_at]
        if rf:
            need(34); draw_signature(c, r, 54, state["y"] - 24, 150, 28, color=brand["primary"]); state["y"] -= 32
            for f in rf:
                line(f"Signature field · doc {f.document_id} page {f.page} · reason: {f.reason or '-'} · field SHA-256 {f.field_hash}", s=6.5, col=muted, indent=18)
    state["y"] -= 4; line("Event history (UTC, hash-chained)", "VSSans-Bold", 10)
    for e in events:
        line(f"{e.created_at:%Y-%m-%d %H:%M:%S}  {e.event:<18} {e.actor}  ip={e.ip or '-'}  {e.detail}", s=6.8, indent=8)
        line(f"entry {e.entry_hash}  prev {e.prev_hash or '-'}", s=5.5, col=muted, indent=18)
    state["y"] -= 6
    line(sealed_note, "VSSans", 7, muted)
    line("Electronic signature: signer authentication + intent + consent + signature appearance + tamper-evident audit trail.", "VSSans", 7, muted)
    line("Not an Aadhaar eSign, DSC or eIDAS qualified signature unless stated per recipient above.", "VSSans", 7, muted)
    c.save(); return buf.getvalue()


def combine(parts: list[bytes]) -> bytes:
    w = PdfWriter()
    for p in parts:
        for pg in PdfReader(io.BytesIO(p)).pages:
            w.add_page(pg)
    out = io.BytesIO(); w.write(out); return out.getvalue()
