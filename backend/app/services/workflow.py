"""Envelope workflow engine: preparation checks, routing (sequential / parallel / mixed), recipient authentication,
completion, decline, void, correction, reminders, expiry and finalization."""
import ast, operator, re
from datetime import timedelta
from fastapi import HTTPException
from ..core.config import settings
from ..core.security import sha256_hex, random_token, numeric_code, keyed_hash
from ..models import Envelope, EnvelopeDocument, Recipient, Field, Organization, User, AuditEvent, now
from . import audit, notify, i18n
from .storage import storage, new_key

ACTING = ("signer", "approver", "viewer", "in_person", "witness", "editor")
SIGNING = ("signer", "in_person", "witness")
OPEN = ("sent", "delivered", "partially_signed")
DEFAULT_ORG_SETTINGS = {
    "envelope_expiry_days": 120, "reminder_first_days": 2, "reminder_every_days": 2, "default_auth": "access_code",
    "allowed_auth": ["none", "access_code", "email_otp", "sms_otp"], "allowed_signature_kinds": ["typed", "drawn", "uploaded"],
    "allowed_signature_types": ["electronic"], "timezone": "Asia/Kolkata", "date_format": "%d %b %Y", "language": "en",
    "require_reason": True, "default_visibility": "private", "mfa_required": False, "password_policy": {},
    "consent_text": "", "privacy_text": "", "retention": {"draft_days": 30, "completed_days": 3650, "declined_days": 365, "voided_days": 365, "expired_days": 365},
    "allow_overage": False, "session_idle_minutes": 30,
}


def org_settings(org: Organization) -> dict:
    s = {**DEFAULT_ORG_SETTINGS, **(org.settings or {})}
    s["retention"] = {**DEFAULT_ORG_SETTINGS["retention"], **((org.settings or {}).get("retention") or {})}
    return s


def public_id() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    import secrets
    return "VS-" + "".join(secrets.choice(alphabet) for _ in range(10))


def doc_bytes(org, d: EnvelopeDocument) -> bytes:
    return storage().get(org.region, d.storage_key)


def add_document(db, org, env, filename: str, data: bytes, req=None, actor: str = "") -> EnvelopeDocument:
    from . import documents
    if env.status != "draft":
        raise HTTPException(409, "Documents can only be changed while the envelope is a draft")
    if len(data) > settings.MAX_DOC_MB * 1024 * 1024:
        raise HTTPException(413, f"Each document must be {settings.MAX_DOC_MB} MB or smaller")
    if len(env.documents) >= settings.MAX_DOCS_PER_ENVELOPE:
        raise HTTPException(422, f"An envelope can contain at most {settings.MAX_DOCS_PER_ENVELOPE} documents")
    if sum(d.size for d in env.documents) + len(data) > settings.MAX_ENVELOPE_MB * 1024 * 1024:
        raise HTTPException(413, f"An envelope can be at most {settings.MAX_ENVELOPE_MB} MB")
    scan = documents.scan_malware(data)
    pdf, src_type = documents.to_pdf(filename, data)
    pages, text = documents.inspect_pdf(pdf)
    key = new_key(org.region, org.id, "original")
    storage().put(org.region, key, pdf)
    name = re.sub(r"\.[A-Za-z0-9]+$", "", filename or "document")[:200] + ".pdf"
    d = EnvelopeDocument(envelope_id=env.id, order=len(env.documents) + 1, name=name, source_name=(filename or "document")[:255], source_type=src_type,
                         storage_key=key, sha256=sha256_hex(pdf), source_sha256=sha256_hex(data), size=len(pdf), pages=pages, text=text)
    db.add(d); env.documents.append(d); db.flush()
    env.version_hash = sha256_hex("|".join(x.sha256 for x in env.documents))
    reindex(env)
    audit.record(db, env, "document_uploaded", actor, req, f"{d.source_name} → {d.name}; {len(pages)} page(s); sha256 {d.sha256}; malware scan: {scan}")
    return d


def reindex(env):
    parts = [env.title, env.public_id, env.message or ""] + [f"{r.name} {r.email}" for r in env.recipients] + [d.name for d in env.documents]
    parts += [f.value for f in env.fields if f.value and f.type not in ("signature", "initials")]
    parts += [d.text[:20000] for d in env.documents]
    env.search_text = "\n".join(p for p in parts if p).lower()[:300000]


def validate_send(env: Envelope, org) -> None:
    errs = []
    if not env.documents: errs.append("Add at least one document")
    acting = [r for r in env.recipients if r.type in ACTING]
    if not acting: errs.append("Add at least one recipient who signs, approves or views")
    s = org_settings(org)
    for r in env.recipients:
        if r.type in SIGNING and not any(f.recipient_id == r.id and f.type == "signature" for f in env.fields):
            errs.append(f"Place at least one signature field for {r.name}")
        if r.auth_method not in s["allowed_auth"]: errs.append(f"Authentication '{r.auth_method}' is not allowed by your organization for {r.name}")
        if r.auth_method == "sms_otp":
            if not r.phone: errs.append(f"{r.name} needs a mobile number for SMS OTP")
        if r.type == "in_person" and not r.host_user_id: errs.append(f"In-person signer {r.name} needs a host")
        if r.signature_type != "electronic":
            from .trust import PROVIDERS
            p = PROVIDERS.get(r.signature_type)
            if not p or not p.configured():
                errs.append(f"{r.signature_type} signing is not available: provider not configured / not implemented")
    if any(f.type == "stamp" for f in env.fields):
        from . import companystamp
        from ..core.db import SessionLocal
        if not companystamp.meta(org): errs.append("No official company stamp is configured. An org admin must upload it in Settings, or remove the Company stamp field")
        from sqlalchemy.orm import object_session
        sdb = object_session(env)
        for r in {f.recipient_id: next(x for x in env.recipients if x.id == f.recipient_id) for f in env.fields if f.type == "stamp"}.values():
            if not companystamp.is_internal(sdb, org, r):
                errs.append(f"The company stamp can only be applied by an internal VAICS signer; {r.name} <{r.email}> is not an active user of your organization")
    if errs:
        raise HTTPException(422, {"code": "not_ready", "errors": errs, "message": "; ".join(errs)})


def send(db, org, env: Envelope, user: User, req=None):
    if env.status != "draft": raise HTTPException(409, "Envelope already sent")
    if org.status in ("suspended", "closed"): raise HTTPException(403, f"Sending is disabled: organization is {org.status}")
    if not user.email_verified: raise HTTPException(403, "Verify your email address before sending documents")
    validate_send(env, org)
    s = org_settings(org)
    env.status, env.sent_at = "sent", now()
    if not env.expires_at: env.expires_at = now() + timedelta(days=int(s["envelope_expiry_days"]))
    env.is_sandbox = org.is_sandbox
    audit.record(db, env, "sent", user.email, req, f"{len(env.recipients)} recipient(s); expires {env.expires_at:%Y-%m-%d}")
    route(db, org, env, req)


def current_step(env: Envelope) -> list[Recipient]:
    pending = [r for r in env.recipients if r.type in ACTING and r.status not in ("completed",)]
    if not pending:
        return []
    o = min(r.order for r in pending)
    return [r for r in pending if r.order == o]


def route(db, org, env, req=None):
    step = current_step(env)
    if not step:
        finalize(db, org, env, req); return
    for r in step:
        if r.status == "created":
            notify_recipient(db, org, env, r, req)


def _issue_link(r: Recipient) -> str:
    tok = random_token(32)
    r.token_hash, r.token_revoked = sha256_hex(tok), False
    r.token_expires_at = None  # bounded by envelope expiry
    r.session_hash = None
    return tok


def signing_url(tok: str) -> str:
    return f"{settings.PUBLIC_APP_URL}/s/{tok}"


def notify_recipient(db, org, env, r: Recipient, req=None, reissue=False):
    owner = db.get(User, env.owner_id)
    lang = r.language or env.language
    r.status, r.notified_at, r.code_attempts, r.code_locked, r.otp_sends = "sent", now(), 0, False, 0
    tok = _issue_link(r)
    if r.type == "in_person":
        host = db.get(User, r.host_user_id)
        notify.notify_user(db, host.id, f"In-person signing ready for {r.name}: {env.title}", env.id)
        notify.send_email(db, org=org, to=host.email, kind="in_person_host", envelope=env, lang=lang,
                          subject=f"Host in-person signing: {env.title}", body=f"You are the host for {r.name}'s in-person signing of \"{env.title}\". Open the envelope in VAICS Sign and start the in-person session.",
                          link=f"{settings.PUBLIC_APP_URL}/envelopes/{env.id}")
        r.token_hash = None  # in-person signing is started by the host only
        audit.record(db, env, "host_notified", "system", req, f"host {host.email} for in-person signer {r.name}", r)
        return
    action = {"approver": "action.approve", "viewer": "action.view"}.get(r.type, "action.sign")
    url = signing_url(tok)
    msg = "\n".join(x for x in (env.message, r.private_message) if x)
    msg = f"\n{msg}\n" if msg else ""
    note = i18n.t("invite.auth_note", lang) if r.auth_method == "access_code" and not r.sender_set_code else ""
    body = i18n.t("invite.body", lang, name=r.name, sender=owner.full_name, title=env.title, action=i18n.t(action, lang),
                  step=f" (step {r.order})", message=msg,
                  auth_note=note, expires=f"{env.expires_at:%d %b %Y}" if env.expires_at else "-")
    m1 = notify.send_email(db, org=org, to=r.email, kind="signing_link", envelope=env, lang=lang, link=url,
                           subject=i18n.t("invite.subject", lang, sender=owner.full_name, title=env.title), body=body)
    detail = f"{'re' if reissue else ''}issued link to {r.email} (email {m1.delivery})"
    if r.auth_method == "access_code" and not r.sender_set_code:
        code = numeric_code(settings.ACCESS_CODE_LENGTH)
        r.code_hash, r.code_expires_at = keyed_hash(f"ac:{r.id}", code), now() + timedelta(hours=settings.ACCESS_CODE_EXPIRY_HOURS)
        if r.phone and org_settings(org).get("access_code_channel") == "sms" and notify.sms_configured():
            m2 = notify.send_sms(db, org=org, to=r.phone, kind="access_code", envelope=env, code=code, body=f"{env.title}: access code {code}")
        else:
            m2 = notify.send_email(db, org=org, to=r.email, kind="access_code", envelope=env, lang=lang, code=code,
                                   subject=i18n.t("code.subject", lang, title=env.title),
                                   body=i18n.t("code.body", lang, name=r.name, title=env.title, hours=settings.ACCESS_CODE_EXPIRY_HOURS, attempts=settings.CODE_MAX_ATTEMPTS))
        detail += f"; access code sent separately ({m2.channel} {m2.delivery})"
    elif r.auth_method == "access_code":
        detail += "; sender-set access code (shared outside the platform)"
    audit.record(db, env, "recipient_notified", "system", req, detail, r)
    if env.status == "sent" and any(x.status == "completed" for x in env.recipients if x.type in ACTING):
        env.status = "partially_signed"


# ---------------- recipient access ----------------
def recipient_by_token(db, tok: str) -> tuple[Envelope, Recipient]:
    r = db.query(Recipient).filter_by(token_hash=sha256_hex(tok)).first()
    if not r or r.token_revoked:
        raise HTTPException(404, "This link is invalid or has been replaced. Ask the sender to resend it.")
    env = db.get(Envelope, r.envelope_id)
    check_expiry(db, env)
    if env.status == "voided": raise HTTPException(410, "This envelope was voided by the sender.")
    if env.status == "declined": raise HTTPException(410, "This envelope was declined and is no longer active.")
    if env.status == "expired": raise HTTPException(410, "This envelope has expired.")
    if env.status not in OPEN: raise HTTPException(409, f"Envelope is {env.status}")
    if r not in current_step(env):
        raise HTTPException(409, {"code": "not_your_turn", "message": "It is not your turn yet. You will receive an email when it is."})
    return env, r


def check_expiry(db, env):
    if env.status in OPEN and env.expires_at and env.expires_at < now():
        env.status = "expired"
        for r in env.recipients: r.token_revoked = True
        audit.record(db, env, "expired", "system")
        owner = db.get(User, env.owner_id)
        notify.notify_user(db, owner.id, f"Envelope expired: {env.title}", env.id)
        db.commit()


def verify_code(db, org, env, r, code: str, req) -> str:
    if r.code_locked:
        raise HTTPException(423, "Too many incorrect codes. The sender has been alerted and must reissue your access.")
    if r.auth_method == "none":
        raise HTTPException(400, "No code required")
    purpose = f"ac:{r.id}" if r.auth_method == "access_code" else f"otp:{r.id}"
    if not r.code_hash: raise HTTPException(400, "Request a code first")
    if r.code_expires_at and r.code_expires_at < now(): raise HTTPException(410, "The code has expired. Request a new one or ask the sender to reissue.")
    import hmac
    if not hmac.compare_digest(keyed_hash(purpose, code.strip()), r.code_hash):
        r.code_attempts += 1
        left = settings.CODE_MAX_ATTEMPTS - r.code_attempts
        audit.record(db, env, "authentication_failed", r.email, req, f"{r.auth_method}; {max(0, left)} attempt(s) left", r)
        if left <= 0:
            r.code_locked = True
            audit.record(db, env, "recipient_locked", r.email, req, "maximum attempts reached", r)
            owner = db.get(User, env.owner_id)
            notify.notify_user(db, owner.id, f"{r.name} is locked out of {env.title} after too many wrong codes.", env.id)
            notify.send_email(db, org=org, to=owner.email, kind="recipient_locked", envelope=env, subject=f"Recipient locked out: {env.title}",
                              body=f"{r.name} ({r.email}) entered too many incorrect codes and is locked out. Reissue access from the envelope page.",
                              link=f"{settings.PUBLIC_APP_URL}/envelopes/{env.id}")
            db.commit()
            raise HTTPException(423, "Too many incorrect codes. The sender has been alerted and must reissue your access.")
        db.commit()
        raise HTTPException(403, {"code": "wrong_code", "attempts_left": left, "message": f"Incorrect code. {left} attempt(s) left."})
    return open_session(db, env, r, req, r.auth_method)


def open_session(db, env, r, req, method: str) -> str:
    sess = random_token(32)
    r.session_hash, r.session_last_seen, r.code_attempts = sha256_hex(sess), now(), 0
    if r.auth_method in ("email_otp", "sms_otp"): r.code_hash = None  # OTP single use
    r.status = "authenticated"
    audit.record(db, env, "authenticated", r.email, req, f"method: {method}", r)
    if env.status == "sent" and not any(x.status == "completed" for x in env.recipients if x.type in ACTING):
        env.status = "delivered"
    return sess


def send_otp(db, org, env, r, req):
    if r.auth_method not in ("email_otp", "sms_otp"): raise HTTPException(400, "This recipient does not use one-time codes")
    if r.code_locked: raise HTTPException(423, "Locked. Ask the sender to reissue access.")
    if r.otp_sends >= 5: raise HTTPException(429, "Too many codes requested. Ask the sender to reissue access.")
    code = numeric_code(6)
    r.code_hash, r.code_expires_at, r.otp_sends = keyed_hash(f"otp:{r.id}", code), now() + timedelta(minutes=settings.OTP_MINUTES), r.otp_sends + 1
    if r.auth_method == "sms_otp":
        m = notify.send_sms(db, org=org, to=r.phone, kind="otp", envelope=env, code=code, body=f"{code} is your VAICS Sign code for {env.title}. Valid {settings.OTP_MINUTES} min.")
    else:
        m = notify.send_email(db, org=org, to=r.email, kind="otp", envelope=env, code=code, lang=r.language,
                              subject=i18n.t("otp.subject", r.language), body=i18n.t("otp.body", r.language, title=env.title, minutes=settings.OTP_MINUTES))
    audit.record(db, env, "otp_sent", "system", req, f"{m.channel} {m.delivery}", r)


def session_recipient(db, tok: str, sess: str | None, idle_minutes: int | None = None):
    env, r = recipient_by_token(db, tok)
    if r.auth_method == "none" and not r.session_hash:
        raise HTTPException(401, {"code": "start_session", "message": "Open the document to begin"})
    if not sess or not r.session_hash or sha256_hex(sess) != r.session_hash:
        raise HTTPException(401, {"code": "auth_required", "message": "Authenticate to open this envelope"})
    idle = idle_minutes or settings.SIGNER_SESSION_MINUTES
    if r.session_last_seen and r.session_last_seen < now() - timedelta(minutes=idle):
        r.session_hash = None; db.commit()
        raise HTTPException(401, {"code": "session_expired", "message": "Your session ended after inactivity. Authenticate again."})
    r.session_last_seen = now()
    return env, r


# ---------------- completing ----------------
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.USub: operator.neg}


def eval_formula(expr: str, values: dict[int, str]) -> str:
    src = re.sub(r"\{(\d+)\}", lambda m: str(float(values.get(int(m.group(1))) or 0)), expr)

    def ev(n):
        if isinstance(n, ast.Expression): return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)): return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS: return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS: return _OPS[type(n.op)](ev(n.operand))
        raise ValueError("unsupported")
    try:
        v = ev(ast.parse(src, mode="eval"))
        return f"{v:.2f}".rstrip("0").rstrip(".")
    except Exception:
        return ""


def field_active(f: Field, values: dict[int, str]) -> bool:
    c = f.condition or {}
    if not c.get("field_id"):
        return True
    return str(values.get(int(c["field_id"]), "")) == str(c.get("equals", ""))


def validate_value(f: Field, v: str) -> str | None:
    if f.validation == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v): return "must be an email address"
    if f.validation == "number" or f.type == "number":
        try: float(v)
        except ValueError: return "must be a number"
    if f.validation == "date" or f.type == "date":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v): return "must be a date (YYYY-MM-DD)"
    india = {"pan": (r"[A-Z]{5}[0-9]{4}[A-Z]", "must be a valid PAN (e.g. ABCDE1234F)"),
             "gstin": (r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", "must be a valid GSTIN"),
             "pincode": (r"[1-9]\d{5}", "must be a 6-digit PIN code"), "phone": (r"\+?[0-9 ()-]{7,20}", "must be a phone number")}
    if f.validation in india and not re.fullmatch(india[f.validation][0], v.strip().upper() if f.validation in ("pan", "gstin") else v.strip()):
        return india[f.validation][1]
    if f.validation == "regex" and f.regex:
        try:
            if not re.fullmatch(f.regex, v): return "has an invalid format"
        except re.error:
            pass
    if f.type in ("dropdown", "radio") and f.options and v not in f.options: return "must be one of the options"
    return None


def complete_recipient(db, org, env, r: Recipient, payload: dict, req, actor_email: str | None = None):
    """payload: consent, signature {kind, style, image, initials}, values {field_id: value}, reasons {field_id: reason}"""
    s = org_settings(org)
    if r.type in SIGNING or r.type == "approver":
        if not payload.get("consent"): raise HTTPException(422, "Accept the electronic record and signature disclosure to continue")
        if r.type in SIGNING and not payload.get("intent"):
            raise HTTPException(422, "Confirm the signature statement (meaning of your signature) to continue")
    sig = payload.get("signature") or {}
    my = [f for f in env.fields if f.recipient_id == r.id]
    all_values = {f.id: f.value for f in env.fields if f.value is not None}
    incoming = {int(k): ("" if v is None else str(v)) for k, v in (payload.get("values") or {}).items()}
    reasons = {int(k): str(v or "").strip() for k, v in (payload.get("reasons") or {}).items()}
    for k in incoming:
        if not any(f.id == k for f in my): raise HTTPException(403, "You can only fill your own fields")
    all_values.update(incoming)
    errors = []
    if any(f.type in ("signature", "initials") for f in my):
        kind = sig.get("kind") or "typed"
        if kind not in s["allowed_signature_kinds"]: errors.append(f"{kind} signatures are not allowed")
        if kind in ("drawn", "uploaded"):
            img = sig.get("image") or ""
            if not re.match(r"^data:image/(png|jpeg);base64,", img) or len(img) > 700_000: errors.append("Provide a PNG/JPEG signature image under 500 KB")
        r.signature_kind, r.signature_style = kind, (sig.get("style") or "great_vibes")[:30]
        r.signature_image = sig.get("image") if kind in ("drawn", "uploaded") else None
        r.initials = (sig.get("initials") or "").strip()[:10] or None
    stamp_meta = None
    if any(f.type == "stamp" for f in my):
        from . import companystamp
        stamp_cur = companystamp.current_image(org)
        stamp_meta = {"sha256": stamp_cur[0]} if stamp_cur else None
        if not stamp_meta: errors.append("Company stamp not configured; ask your admin to upload it")
        elif not companystamp.is_internal(db, org, r): errors.append("Only an internal VAICS signer can apply the company stamp")
    ts = now()
    for f in my:
        if f.type == "formula":
            continue
        active = field_active(f, all_values)
        if f.type == "signature":
            reason = reasons.get(f.id, "")
            if f.reason_required and s.get("require_reason", True) and not reason: errors.append("Enter a reason under every signature")
            f.reason = reason[:200] or None
            f.value = r.name
        elif f.type == "initials":
            f.value = r.initials or "".join(p[0] for p in r.name.split() if p).upper()
        elif f.type == "date_signed":
            f.value = ts.strftime(s["date_format"])
        elif f.type == "stamp":
            f.value = f"sha256:{stamp_meta['sha256']}" if stamp_meta else None  # never taken from signer input
        elif f.type == "name": f.value = r.name
        elif f.type == "email": f.value = r.email
        elif f.read_only:
            f.value = f.default_value
        else:
            v = incoming.get(f.id, f.value if f.value is not None else (f.default_value or "")).strip()
            if f.type == "checkbox":
                v = "true" if v in ("true", "1", "on", "yes", "X") else ""
            if active and f.required and not v:
                errors.append(f"{f.label or f.type} is required")
            elif v:
                e = validate_value(f, v)
                if e: errors.append(f"{f.label or f.type} {e}")
            f.value = v if active else None
    if errors:
        raise HTTPException(422, {"code": "invalid_fields", "errors": sorted(set(errors)), "message": "; ".join(sorted(set(errors)))})
    if stamp_meta:
        companystamp.snapshot(org, env.id, stamp_cur[0], stamp_cur[1])
    vals = {f.id: f.value for f in env.fields}
    for f in my:
        if f.type == "formula" and f.formula:
            f.value = eval_formula(f.formula, vals)
    prev_version = env.version_hash
    for f in sorted(my, key=lambda x: x.id):
        f.signed_at = ts
        f.field_hash = sha256_hex(f"{prev_version}|{r.id}|{r.email}|{r.name}|{f.id}|{f.type}|{ts.isoformat()}Z|{f.reason or ''}|{f.value or ''}")
    env.version_hash = sha256_hex(prev_version + "".join(f.field_hash for f in sorted(my, key=lambda x: x.id)))
    for f in sorted(my, key=lambda x: x.id):
        if f.type == "stamp" and f.value:
            audit.record(db, env, "company_stamp_applied", actor_email or r.email, req,
                         f"official company stamp applied by {r.name} <{r.email}> on field {f.id} (page {f.page}); image {f.value}", r)
    if r.consent_at is None and payload.get("consent"):
        r.consent_at = ts
        audit.record(db, env, "consent_given", r.email, req, "electronic record and signature disclosure accepted", r)
    if payload.get("intent"):
        meaning = (payload.get("signature_meaning") or "Approved").strip()[:60]
        audit.record(db, env, "signature_intent_affirmed", r.email, req, f"signer affirmed intent to sign electronically; meaning: {meaning}", r)
    r.status, r.completed_at = "completed", ts
    r.completed_ip, r.completed_ua = audit.client_ip(req), (req.headers.get("user-agent", "")[:300] if req else None)
    r.token_revoked, r.session_hash = True, None
    ev = {"signer": "signed", "in_person": "signed_in_person", "witness": "witnessed", "approver": "approved", "viewer": "viewed_ack", "editor": "edited"}[r.type]
    audit.record(db, env, ev, actor_email or r.email, req, f"{len(my)} field(s); signature {r.signature_kind or '-'}; version {env.version_hash}", r)
    reindex(env)
    owner = db.get(User, env.owner_id)
    if (env.sender_notify or {}).get("signed", True):
        notify.notify_user(db, owner.id, f"{r.name} completed {env.title}", env.id)
    if env.status in ("sent", "delivered"):
        env.status = "partially_signed"
    route(db, org, env, req)


def decline(db, org, env, r, reason: str, req):
    if not reason.strip(): raise HTTPException(422, "Give a reason for declining")
    r.status, r.decline_reason = "declined", reason.strip()[:1000]
    env.status = "declined"
    for x in env.recipients: x.token_revoked, x.session_hash = True, None
    audit.record(db, env, "declined", r.email, req, reason[:300], r)
    owner = db.get(User, env.owner_id)
    notify.notify_user(db, owner.id, f"{r.name} declined {env.title}", env.id)
    notify.send_email(db, org=org, to=owner.email, kind="declined", envelope=env, subject=f"Declined: {env.title}",
                      body=f"{r.name} ({r.email}) declined \"{env.title}\".\nReason: {reason}", link=f"{settings.PUBLIC_APP_URL}/envelopes/{env.id}")


def void(db, org, env, user, reason: str, req):
    if env.status not in OPEN: raise HTTPException(409, "Only envelopes in progress can be voided")
    if not reason.strip(): raise HTTPException(422, "A reason is required to void")
    env.status, env.void_reason = "voided", reason.strip()[:1000]
    for r in env.recipients:
        notified = r.notified_at is not None and r.status != "completed"
        r.token_revoked, r.session_hash = True, None
        if notified or r.status == "completed":
            notify.send_email(db, org=org, to=r.email, kind="voided", envelope=env, subject=f"Voided: {env.title}",
                              body=f"Hello {r.name},\n\nThe sender voided \"{env.title}\". Reason: {reason}\nNo further action is needed.")
    audit.record(db, env, "voided", user.email, req, reason[:300])


def reissue(db, org, env, r, user, req, new_code: str | None = None):
    if env.status not in OPEN or r not in current_step(env):
        raise HTTPException(409, "Access can only be reissued for a recipient whose turn it is")
    r.token_revoked = True
    audit.record(db, env, "access_revoked", user.email, req, f"previous link/code for {r.email} revoked", r)
    r.status = "created"
    if new_code:
        r.code_hash, r.code_expires_at = keyed_hash(f"ac:{r.id}", new_code), now() + timedelta(hours=settings.ACCESS_CODE_EXPIRY_HOURS)
    notify_recipient(db, org, env, r, req, reissue=True)


def remind(db, org, env, r, req, actor="system"):
    if r.status in ("completed", "declined") or r not in current_step(env) or r.type == "in_person":
        return False
    tok = _issue_link(r)  # fresh link (old reminder links stop working; codes remain valid)
    notify.send_email(db, org=org, to=r.email, kind="reminder", envelope=env, link=signing_url(tok), lang=r.language,
                      subject=i18n.t("reminder.subject", r.language, title=env.title), body=f"Hello {r.name},\n\n\"{env.title}\" is still waiting for you. Use the link below; use the access code you received earlier.")
    r.last_reminded_at, r.reminders_sent = now(), r.reminders_sent + 1
    audit.record(db, env, "reminder_sent", actor, req, r.email, r)
    return True


def correct(db, org, env, user, data: dict, req):
    """Correct unsigned recipients, message, expiry and fields of unsigned recipients after sending (FR-056)."""
    if env.status not in OPEN: raise HTTPException(409, "Only envelopes in progress can be corrected")
    changes = []
    if "message" in data and data["message"] is not None: env.message = data["message"]; changes.append("message")
    if data.get("expires_at"):
        from datetime import datetime
        env.expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "")); env.expiry_warned = False; changes.append(f"expiry → {env.expires_at:%Y-%m-%d}")
    renotify = []
    for rc in data.get("recipients") or []:
        r = next((x for x in env.recipients if x.id == rc.get("id")), None)
        if not r: raise HTTPException(404, "Recipient not found")
        if r.status == "completed": raise HTTPException(409, f"{r.name} has already completed and cannot be changed")
        before = (r.name, r.email, r.phone)
        for k in ("name", "email", "phone", "private_message"):
            if rc.get(k) is not None: setattr(r, k, rc[k].strip() if isinstance(rc[k], str) else rc[k])
        if (r.name, r.email, r.phone) != before:
            changes.append(f"recipient {before[1]} → {r.email}")
            r.email_status = None
            if r in current_step(env): renotify.append(r)
    for fc in data.get("fields") or []:
        f = next((x for x in env.fields if x.id == fc.get("id")), None)
        if not f: raise HTTPException(404, "Field not found")
        owner_r = next(x for x in env.recipients if x.id == f.recipient_id)
        if owner_r.status == "completed": raise HTTPException(409, "Fields of completed recipients cannot be changed")
        for k in ("x", "y", "w", "h", "page", "required", "label", "default_value"):
            if k in fc: setattr(f, k, fc[k])
        changes.append(f"field {f.id}")
    audit.record(db, env, "corrected", user.email, req, "; ".join(changes) or "no changes")
    for r in renotify:
        r.token_revoked = True; r.status = "created"
        notify_recipient(db, org, env, r, req, reissue=True)
    reindex(env)


# ---------------- finalization ----------------
def _stamp_loader(org, env):
    from . import companystamp
    return lambda sha: companystamp.load_applied(org, env.id, sha)


def finalize(db, org, env, req=None):
    from . import pdfstamp, seal as sealmod
    owner = db.get(User, env.owner_id)
    s = org_settings(org)
    brand = notify.brand_of(org, env)
    rmap = {r.id: r for r in env.recipients}
    env.completed_at = now()
    env.status = "completed"
    stamped = []
    for d in env.documents:
        stamped.append(pdfstamp.stamp_document(doc_bytes(org, d), [f for f in env.fields if f.document_id == d.id], rmap, s["timezone"], brand, stamp_loader=_stamp_loader(org, env)))
    audit.record(db, env, "completed", "system", req, f"all {len([r for r in env.recipients if r.type in ACTING])} recipient(s) completed")
    mode = sealmod.seal_mode()
    note = {"no": "This PDF is NOT sealed with a PAdES signature (no seal certificate configured).",
            "pades_dev_selfsigned": "Sealed with a DEVELOPMENT self-signed PAdES seal: tamper-evident, but not issued by a trusted CA.",
            "pades": "Sealed with the platform PAdES document-signing certificate (no trusted timestamp configured).",
            "pades_timestamped": "Sealed with the platform PAdES certificate and an RFC 3161 trusted timestamp (B-T)."}[mode]
    events = db.query(AuditEvent).filter_by(envelope_id=env.id).order_by(AuditEvent.id).all()
    cert = pdfstamp.certificate(env, env.documents, env.recipients, env.fields, events, owner, brand, s["timezone"], note)
    combined = pdfstamp.combine(stamped + [cert])
    try:
        sealed_pdf, mode = sealmod.seal(combined, reason=f"{brand['product_name']} envelope {env.public_id} completed", location=org.name)
    except Exception as ex:  # noqa: BLE001
        sealed_pdf, mode = combined, "no"
        audit.record(db, env, "seal_failed", "system", req, str(ex)[:200])
    env.sealed = mode
    key = new_key(org.region, org.id, "completed")
    storage().put(org.region, key, sealed_pdf, worm=True)
    ckey = new_key(org.region, org.id, "certificate")
    storage().put(org.region, ckey, cert, worm=True)
    env.completed_key, env.certificate_key, env.completed_sha256 = key, ckey, sha256_hex(sealed_pdf)
    audit.record(db, env, "finalized", "system", req, f"seal={mode}; completed sha256 {env.completed_sha256}")
    attach = [(f"{env.public_id}-signed.pdf", sealed_pdf)] if len(sealed_pdf) <= settings.EMAIL_ATTACH_MAX_MB * 1024 * 1024 else []
    note_attach = "The signed PDF and Certificate of Completion are attached." if attach else "Download the signed PDF using the secure link below."
    parties = [(owner.email, owner.full_name, f"{settings.PUBLIC_APP_URL}/envelopes/{env.id}", owner.language)]
    for r in env.recipients:
        if r.type == "in_person" and not r.email: continue
        dt = random_token(32)
        r.download_hash, r.download_expires_at = sha256_hex(dt), now() + timedelta(days=30)
        parties.append((r.email, r.name, f"{settings.PUBLIC_APP_URL}/completed/{dt}", r.language))
    seen = set()
    for email, name, link, lang in parties:
        if email.lower() in seen: continue
        seen.add(email.lower())
        notify.send_email(db, org=org, to=email, kind="completed", envelope=env, link=link, attachments=attach if notify.smtp_configured() else [(a[0], b"") for a in attach],
                          lang=lang, subject=i18n.t("completed.subject", lang, title=env.title),
                          body=i18n.t("completed.body", lang, name=name, title=env.title, envelope_id=env.public_id, attach_note=note_attach, hash=env.completed_sha256))
    audit.record(db, env, "completion_delivered", "system", req, f"{len(seen)} part(ies): {', '.join(sorted(seen))}")
    notify.notify_user(db, owner.id, f"Completed: {env.title}", env.id)
