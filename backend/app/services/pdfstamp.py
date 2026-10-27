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


def draw_signature(c, r, x, y, w, h, initials=False, color="#000000"):
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


def stamp_document(src: bytes, fields, recipients: dict, tz: str, brand: dict, stamp_loader=None) -> bytes:
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
                draw_signature(c, r, bx + 1, by + text_h, bw - 2, max(6, bh - text_h - 1), color="#000000")
                yy = by + 2 + small * 1.22 * (len(lines) - 1)
                for txt, font in lines:
                    c.setFillColor(ink if font.endswith("Bold") else muted); c.setFont(font, _fit(txt, font, small, bw - 4)); c.drawString(bx + 2, yy, txt); yy -= small * 1.22
            elif f.type == "initials":
                draw_signature(c, r, bx, by, bw, bh, initials=True, color="#000000")
            elif f.type == "checkbox":
                c.setStrokeColor(ink); s = min(bw, bh); c.rect(bx, by + bh - s, s, s)
                if f.value in ("true", "1", "X", "on", "yes"):
                    c.setFont("VSSans-Bold", s * 0.9); c.setFillColor(ink); c.drawString(bx + s * 0.15, by + bh - s * 0.85, "✓")
            elif f.type == "stamp":
                # official company stamp image (aspect fit, centred); legacy text-only values are not drawn
                if stamp_loader and str(f.value or "").startswith("sha256:"):
                    img = ImageReader(io.BytesIO(stamp_loader(f.value.split(":", 1)[1])))
                    c.drawImage(img, bx, by, width=bw, height=bh, mask="auto", preserveAspectRatio=True, anchor="c")
            elif f.type == "attachment":
                txt = f"Attachment: {f.value}"; c.setFillColor(muted); c.setFont("VSSans", _fit(txt, "VSSans", f.font_size or 9, bw - 2)); c.drawString(bx + 1, by + 2, txt)
            else:
                txt = str(f.value); size = _fit(txt, "VSSans", min(f.font_size or 10, bh * 0.8), bw - 2)
                c.setFillColor(ink); c.setFont("VSSans", size); c.drawString(bx + 1, by + max(1, (bh - size) / 2), txt)
        c.save(); buf.seek(0)
        page.merge_transformed_page(PdfReader(buf).pages[0], tm)
        writer.add_page(page)
    out = io.BytesIO(); writer.write(out); return out.getvalue()


SKY = "#00B6F0"


def _mix(c1, c2, t):
    a, b = HexColor(c1), HexColor(c2)
    return HexColor((int((a.red + (b.red - a.red) * t) * 255) << 16) | (int((a.green + (b.green - a.green) * t) * 255) << 8) | int((a.blue + (b.blue - a.blue) * t) * 255))


def _gradient_rule(c, x, y, w, h, stops):
    n = 120; seg = w / n
    for i in range(n):
        t = i / (n - 1) * (len(stops) - 1); k = min(int(t), len(stops) - 2)
        c.setFillColor(_mix(stops[k], stops[k + 1], t - k)); c.rect(x + i * seg, y, seg + 0.4, h, fill=1, stroke=0)


def certificate(env, docs, recipients, fields, events, owner, brand: dict, tz: str, sealed_note: str) -> bytes:
    """Certificate of Completion. Visual layout only; every evidence value is printed as stored."""
    from reportlab.lib.utils import simpleSplit
    _fonts()
    W, H = A4; M = 42; CW = W - 2 * M
    primary, accent = brand["primary"], brand["accent"]
    blue, mag, ink, muted, faint = HexColor(primary), HexColor(accent), HexColor("#0F172A"), HexColor("#475569"), HexColor("#94A3B8")
    line_c, card_bg, zebra = HexColor("#D6E8FF"), HexColor("#F7FAFF"), HexColor("#F5F8FC")
    SANS, BOLD, MONO = "VSSans", "VSSans-Bold", "Courier"
    logo = os.path.join(ASSETS, "vaics-logo-full.png")

    def footer(cv, i, n):
        cv.setStrokeColor(line_c); cv.setLineWidth(0.5); cv.line(M, 34, W - M, 34)
        cv.setFillColor(faint); cv.setFont(SANS, 6.5)
        cv.drawString(M, 24, f"{brand['product_name']} · Certificate of Completion · Envelope {env.public_id} · verify at /verify")
        cv.drawRightString(W - M, 24, f"Page {i} of {n}")
        cv.setFont(MONO, 5.5); cv.drawString(M, 16, f"Final document version hash (SHA-256): {env.version_hash or '-'}")

    class _Canvas(canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k); self._pages = []
        def showPage(self):
            self._pages.append(dict(self.__dict__)); self._startPage()
        def save(self):
            n = len(self._pages)
            for i, st in enumerate(self._pages, 1):
                self.__dict__.update(st); footer(self, i, n); canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)

    buf = io.BytesIO(); c = _Canvas(buf, pagesize=A4)
    state = {"y": 0, "first": True}

    def header():
        top = H - 40
        if state["first"]:
            if os.path.exists(logo):
                c.drawImage(ImageReader(logo), M, top - 30, width=133, height=30, mask="auto", preserveAspectRatio=True, anchor="w")
            c.setFillColor(muted); c.setFont(SANS, 7.5); c.drawRightString(W - M, top - 8, brand["org_name"])
            c.setFillColor(faint); c.setFont(SANS, 6.5); c.drawRightString(W - M, top - 19, brand["product_name"])
            c.setFillColor(mag); c.setFont(BOLD, 7); c.drawString(M, top - 52, "E L E C T R O N I C   S I G N A T U R E   R E C O R D")
            c.setFillColor(blue); c.setFont(BOLD, 22); c.drawString(M, top - 76, "Certificate of Completion")
            _gradient_rule(c, M, top - 88, CW, 2, [primary, SKY, accent])
            state["y"] = top - 110; state["first"] = False
        else:
            c.setFillColor(blue); c.setFont(BOLD, 9); c.drawString(M, top - 6, "Certificate of Completion")
            c.setFillColor(muted); c.setFont(SANS, 7); c.drawRightString(W - M, top - 6, f"{env.title} · {env.public_id}"[:110])
            _gradient_rule(c, M, top - 14, CW, 1.2, [primary, SKY, accent])
            state["y"] = top - 34

    def need(hh):
        if state["y"] - hh < 50:
            c.showPage(); header()

    def section(t):
        need(40); state["y"] -= 6
        c.setFillColor(blue); c.setFont(BOLD, 8.5); c.drawString(M, state["y"], t.upper())
        c.setFillColor(mag); c.rect(M, state["y"] - 5, 22, 1.4, fill=1, stroke=0)
        state["y"] -= 18

    def wrap(t, f, sz, w):
        out = []
        for ln in simpleSplit(str(t), f, sz, w) or [""]:
            while pdfmetrics.stringWidth(ln, f, sz) > w and len(ln) > 1:  # break long unspaced tokens (hashes, ids)
                k = len(ln)
                while k > 1 and pdfmetrics.stringWidth(ln[:k], f, sz) > w: k -= 1
                out.append(ln[:k]); ln = ln[k:]
            out.append(ln)
        return out

    def card(x, y, w, h):
        c.setFillColor(card_bg); c.setStrokeColor(line_c); c.setLineWidth(0.6); c.roundRect(x, y - h, w, h, 6, fill=1, stroke=1)

    header()
    # ---- summary
    sent = fmt_times(env.sent_at, tz) if env.sent_at else ("-", "-")
    done = fmt_times(env.completed_at, tz) if env.completed_at else ("-", "-")
    colw = (CW - 36) / 2
    left = [("Envelope", env.title), ("Envelope ID", env.public_id), ("Organization", brand["org_name"]), ("Sender", f"{owner.full_name} <{owner.email}>")]
    right = [("Status", env.status), ("Sent", f"{sent[0]}\n{sent[1]}"), ("Completed", f"{done[0]}\n{done[1]}")]
    def kv_lines(items):
        out = []
        for k, v in items:
            out.append((k, [ln for part in str(v).split("\n") for ln in wrap(part, BOLD if k == "Envelope" else SANS, 9 if k == "Envelope" else 8, colw - 70)]))
        return out
    L, R = kv_lines(left), kv_lines(right)
    hgt = lambda rows: sum(max(1, len(v)) * 11 + 5 for _, v in rows)
    hash_lines = wrap(env.version_hash or "-", MONO, 7, CW - 24)
    ch = max(hgt(L), hgt(R)) + 28 + 12 * len(hash_lines) + 14
    need(ch); y0 = state["y"]; card(M, y0, CW, ch)
    for col, rows in ((0, L), (1, R)):
        yy = y0 - 18; xx = M + 12 + col * (colw + 12)
        for k, vals in rows:
            c.setFillColor(faint); c.setFont(SANS, 6.8); c.drawString(xx, yy, k.upper())
            for j, v in enumerate(vals):
                if k == "Status":
                    tw = pdfmetrics.stringWidth(v, BOLD, 7.5) + 12
                    c.setFillColor(HexColor("#E7F6EE") if v == "completed" else HexColor("#F1F5F9")); c.roundRect(xx + 70, yy - 3.5, tw, 11, 5.5, fill=1, stroke=0)
                    c.setFillColor(HexColor("#047857") if v == "completed" else ink); c.setFont(BOLD, 7.5); c.drawString(xx + 76, yy, v)
                else:
                    c.setFillColor(ink if j == 0 else muted); c.setFont(BOLD if k == "Envelope" else SANS, 9 if k == "Envelope" else (8 if j == 0 else 7)); c.drawString(xx + 70, yy, v)
                yy -= 11
            yy -= 5
    yy = y0 - ch + 14 + 12 * len(hash_lines)
    c.setStrokeColor(line_c); c.line(M + 12, yy + 10, W - M - 12, yy + 10)
    c.setFillColor(faint); c.setFont(SANS, 6.8); c.drawString(M + 12, yy, "FINAL DOCUMENT VERSION HASH (SHA-256)"); yy -= 11
    for hl in hash_lines:
        c.setFillColor(ink); c.setFont(MONO, 7); c.drawString(M + 12, yy, hl); yy -= 12
    state["y"] = y0 - ch - 12

    # ---- documents
    section("Documents")
    for d in docs:
        rows = wrap(f"{d.order}. {d.name} — {len(d.pages)} page(s)", BOLD, 8, CW - 16)
        extra = [] if not (d.source_sha256 and d.source_sha256 != d.sha256) else wrap(f"uploaded as {d.source_name} (SHA-256 {d.source_sha256}), converted to PDF", SANS, 6.8, CW - 16)
        need(14 * len(rows) + 12 + 10 * len(extra))
        for r_ in rows:
            c.setFillColor(ink); c.setFont(BOLD, 8); c.drawString(M + 4, state["y"], r_); state["y"] -= 11
        c.setFillColor(muted); c.setFont(SANS, 6.8); c.drawString(M + 4, state["y"], "Original SHA-256"); c.setFont(MONO, 6.8); c.drawString(M + 70, state["y"], d.sha256 or "-"); state["y"] -= 10
        for e_ in extra:
            c.setFont(SANS, 6.8); c.setFillColor(muted); c.drawString(M + 4, state["y"], e_); state["y"] -= 10
        state["y"] -= 6

    # ---- recipients (two-column cards)
    section("Signers & recipients")
    cw = (CW - 14) / 2; inner = cw - 20
    auth_map = {"none": "email link only", "access_code": "link + separately delivered access code", "email_otp": "link + email one-time code", "sms_otp": "link + SMS one-time code"}
    def build(r):
        items = []  # (kind, payload)
        auth = auth_map.get(r.auth_method, r.auth_method)
        if r.type == "in_person": auth = f"in-person, hosted (host verified ID: {r.id_verification.get('id_type', '-')} {r.id_verification.get('id_last4', '')})"
        items.append(("head", r))
        items += [("name", ln) for ln in wrap(r.name, BOLD, 10, inner)]
        items += [("sub", ln) for ln in wrap(f"{r.email}{' · ' + r.role_name if r.role_name else ''}", SANS, 7.5, inner)]
        kv = [("Authentication", auth), ("Signature type", r.signature_type)]
        if r.completed_at:
            loc, utc = fmt_times(r.completed_at, tz)
            kv += [("Completed", f"{loc}\n{utc}"), ("IP address", r.completed_ip or "-"),
                   ("Consent to e-records", fmt_times(r.consent_at, tz)[1] if r.consent_at else "-"), ("Device", (r.completed_ua or "-")[:90])]
        for k, v in kv:
            for j, ln in enumerate([l for part in str(v).split("\n") for l in wrap(part, SANS, 7, inner - 72)]):
                items.append(("kv", (k if j == 0 else "", ln)))
        if r.decline_reason:
            items += [("decl", ln) for ln in wrap(f"Declined: {r.decline_reason}", SANS, 7.2, inner)]
        rf = [f for f in fields if f.recipient_id == r.id and f.type == "signature" and f.signed_at]
        if rf:
            items.append(("sig", r))
            for f in rf:
                items.append(("fmeta", f"Signature field · doc {f.document_id} · page {f.page}"))
                items += [("reason", ln) for ln in wrap(f"Reason: {f.reason or '-'}", SANS, 7, inner)]
                items += [("mono", ln) for ln in wrap(f"Field SHA-256 {f.field_hash}", MONO, 5.6, inner)]
        sf = [f for f in fields if f.recipient_id == r.id and f.type == "stamp" and f.signed_at and f.value]
        for f in sf:
            items.append(("fmeta", f"Official company stamp applied · doc {f.document_id} · page {f.page}"))
            items += [("mono", ln) for ln in wrap(f"Stamp image {f.value}", MONO, 5.6, inner)]
            items += [("mono", ln) for ln in wrap(f"Field SHA-256 {f.field_hash}", MONO, 5.6, inner)]
        return items
    LH = {"head": 16, "name": 13, "sub": 10, "kv": 9.5, "decl": 10, "sig": 52, "fmeta": 12, "reason": 9.5, "mono": 8}
    def height(items): return 22 + sum(LH[k] for k, _ in items)
    def draw(items, x, y, h):
        card(x, y, cw, h); c.setFillColor(blue); c.roundRect(x, y - h, 3, h, 1.5, fill=1, stroke=0)
        yy = y - 18; xi = x + 12
        for k, v in items:
            if k == "head":
                lab = f"STEP {v.order}"; tw = pdfmetrics.stringWidth(lab, BOLD, 6.5) + 10
                c.setFillColor(blue); c.roundRect(xi, yy - 3, tw, 10.5, 5, fill=1, stroke=0)
                c.setFillColor(HexColor("#FFFFFF")); c.setFont(BOLD, 6.5); c.drawString(xi + 5, yy, lab)
                c.setFillColor(muted); c.setFont(SANS, 7); c.drawString(xi + tw + 6, yy, v.type)
                c.setFillColor(HexColor("#047857") if v.status in ("completed", "signed") else (HexColor("#B91C1C") if v.status == "declined" else muted)); c.setFont(BOLD, 7); c.drawRightString(x + cw - 10, yy, v.status)
            elif k == "name": c.setFillColor(ink); c.setFont(BOLD, 10); c.drawString(xi, yy, v)
            elif k == "sub": c.setFillColor(muted); c.setFont(SANS, 7.5); c.drawString(xi, yy, v)
            elif k == "kv":
                c.setFillColor(faint); c.setFont(SANS, 6.5); c.drawString(xi, yy, v[0])
                c.setFillColor(ink); c.setFont(SANS, 7); c.drawString(xi + 72, yy, v[1])
            elif k == "decl": c.setFillColor(HexColor("#B91C1C")); c.setFont(SANS, 7.2); c.drawString(xi, yy, v)
            elif k == "sig":
                bw, bh = min(inner, 190), 40
                c.setFillColor(HexColor("#FFFFFF")); c.setStrokeColor(line_c); c.setLineWidth(0.6); c.roundRect(xi, yy - bh + 6, bw, bh, 4, fill=1, stroke=1)
                c.setStrokeColor(faint); c.setDash(1.5, 2); c.line(xi + 8, yy - bh + 14, xi + bw - 8, yy - bh + 14); c.setDash()
                draw_signature(c, v, xi + 8, yy - bh + 15, bw - 16, bh - 12, color="#000000")
            elif k == "fmeta": c.setFillColor(blue); c.setFont(BOLD, 7); c.drawString(xi, yy, v)
            elif k == "reason": c.setFillColor(ink); c.setFont(SANS, 7); c.drawString(xi, yy, v)
            elif k == "mono": c.setFillColor(muted); c.setFont(MONO, 5.6); c.drawString(xi, yy, v)
            yy -= LH[k]
    cards = [build(r) for r in sorted(recipients, key=lambda r: (r.order, r.id))]
    for i in range(0, len(cards), 2):
        pair = cards[i:i + 2]; h = max(height(p) for p in pair)
        need(h + 12); y0 = state["y"]
        for j, items in enumerate(pair): draw(items, M + j * (cw + 14), y0, h)
        state["y"] = y0 - h - 12

    # ---- event history
    section("Event history (UTC, hash-chained)")
    cols = [("Time (UTC)", 66), ("Event", 110), ("Actor", 104), ("IP", 50)]; dx = M + 6 + sum(w for _, w in cols); dw = W - M - 6 - dx
    def thead():
        c.setFillColor(HexColor("#EEF4FC")); c.rect(M, state["y"] - 4, CW, 14, fill=1, stroke=0)
        x = M + 6; c.setFillColor(blue); c.setFont(BOLD, 6.5)
        for t_, w in cols: c.drawString(x, state["y"], t_.upper()); x += w
        c.drawString(dx, state["y"], "DETAIL"); state["y"] -= 16
    need(30); thead()
    for n_, e in enumerate(events):
        cells = [wrap(f"{e.created_at:%Y-%m-%d %H:%M:%S}", SANS, 6.6, cols[0][1] - 6), wrap(e.event, BOLD, 6.6, cols[1][1] - 6), wrap(e.actor or "-", SANS, 6.6, cols[2][1] - 6), wrap(e.ip or "-", SANS, 6.6, cols[3][1] - 6), wrap(e.detail or "", SANS, 6.6, dw)]
        hl = wrap(f"entry {e.entry_hash}  prev {e.prev_hash or '-'}", MONO, 5.2, CW - 12)
        rh = 9 * max(len(x) for x in cells) + 7.5 * len(hl) + 6
        if state["y"] - rh < 50: c.showPage(); header(); thead()
        top = state["y"]
        if n_ % 2: c.setFillColor(zebra); c.rect(M, top - rh + 9, CW, rh, fill=1, stroke=0)
        x = M + 6
        for ci, cell in enumerate(cells):
            yy = top
            for ln in cell:
                c.setFillColor(ink if ci in (1, 4) else muted); c.setFont(BOLD if ci == 1 else SANS, 6.6); c.drawString(x if ci < 4 else dx, yy, ln); yy -= 9
            if ci < 4: x += cols[ci][1]
        yy = top - 9 * max(len(x_) for x_ in cells)
        for ln in hl:
            c.setFillColor(faint); c.setFont(MONO, 5.2); c.drawString(M + 6, yy, ln); yy -= 7.5
        state["y"] = top - rh

    # ---- closing notes
    notes = [sealed_note, "Electronic signature: signer authentication + intent + consent + signature appearance + tamper-evident audit trail.",
             "Not an Aadhaar eSign, DSC or eIDAS qualified signature unless stated per recipient above."]
    lines = [ln for t_ in notes for ln in wrap(t_, SANS, 7, CW - 24)]
    ch = 20 + 10 * len(lines); state["y"] -= 10; need(ch); y0 = state["y"]
    card(M, y0, CW, ch); c.setFillColor(mag); c.roundRect(M, y0 - ch, 3, ch, 1.5, fill=1, stroke=0)
    yy = y0 - 14
    for ln in lines:
        c.setFillColor(muted); c.setFont(SANS, 7); c.drawString(M + 12, yy, ln); yy -= 10
    c.showPage(); c.save(); return buf.getvalue()


def combine(parts: list[bytes]) -> bytes:
    w = PdfWriter()
    for p in parts:
        for pg in PdfReader(io.BytesIO(p)).pages:
            w.add_page(pg)
    out = io.BytesIO(); w.write(out); return out.getvalue()
