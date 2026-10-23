"""Sign-up, email verification, login with lockout + MFA (TOTP), sessions, password reset, invitations."""
import re, secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field as PField
from sqlalchemy.orm import Session
from ..core.config import settings
from ..core.db import get_db
from ..core.security import (hash_password, verify_password, create_access_token, random_token, sha256_hex, password_problems,
                             new_totp_secret, verify_totp, totp_uri)
from ..models import User, Organization, Plan, UserSession, OneTimeToken, Invitation, LegalAcceptance, now
from ..services import notify, audit
from ..services.workflow import org_settings
from .deps import get_principal, Principal

router = APIRouter(prefix="/auth", tags=["auth"])
LEGAL_VERSIONS = {"tos": "2026-10", "privacy": "2026-10", "dpa": "2026-10"}
REGION_BY_COUNTRY = {"IN": "in", "US": "us", "CA": "us", "MX": "us", "BR": "us"}
EU = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "GB", "CH", "NO", "IS"}
CURRENCY = {"IN": "INR", "US": "USD"}


def region_for(country: str) -> str:
    c = country.upper()
    return "eu" if c in EU else REGION_BY_COUNTRY.get(c, "us")


def issue_token(db, kind, hours=None, minutes=None, **kw) -> str:
    raw = random_token(32)
    exp = now() + (timedelta(minutes=minutes) if minutes else timedelta(hours=hours or settings.EMAIL_TOKEN_HOURS))
    t = OneTimeToken(kind=kind, token_hash=sha256_hex(raw), expires_at=exp, **kw)
    db.add(t); db.flush()
    return raw, t


def use_token(db, kind, raw) -> OneTimeToken:
    t = db.query(OneTimeToken).filter_by(kind=kind, token_hash=sha256_hex(raw)).first()
    if not t or t.revoked or t.used_at or t.expires_at < now():
        raise HTTPException(400, "This link is invalid or has expired")
    t.used_at = now()
    return t


def send_verification(db, user, org):
    raw, _ = issue_token(db, "verify_email", user_id=user.id)
    notify.send_email(db, org=org, to=user.email, kind="verify_email", subject="Verify your email for VAICS Sign",
                      body=f"Hello {user.full_name},\n\nConfirm your email address to start sending documents. The link expires in {settings.EMAIL_TOKEN_HOURS} hours.",
                      link=f"{settings.PUBLIC_APP_URL}/verify-email/{raw}")


def user_out(u: User, org: Organization | None = None) -> dict:
    d = {k: getattr(u, k) for k in ("id", "email", "full_name", "title", "company", "role", "email_verified", "mfa_enabled", "language", "timezone", "onboarding_done", "org_id", "notify_prefs")}
    if org:
        d["org"] = {"id": org.id, "name": org.name, "slug": org.slug, "status": org.status, "region": org.region, "country": org.country,
                    "plan": org.plan.code if org.plan else None, "plan_name": org.plan.name if org.plan else None, "features": (org.plan.features if org.plan else {}),
                    "trial_ends_at": org.trial_ends_at, "is_sandbox": org.is_sandbox, "branding": notify.brand_of(org)}
    return d


def slugify(name: str, db) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "org"
    slug, i = base, 1
    while db.query(Organization).filter_by(slug=slug).first():
        i += 1; slug = f"{base}-{i}"
    return slug


class SignupIn(BaseModel):
    full_name: str = PField(min_length=2, max_length=120)
    email: EmailStr
    password: str
    organization: str = PField(min_length=2, max_length=200)
    country: str = PField(min_length=2, max_length=2)
    accept_terms: bool
    sandbox: bool = False


@router.post("/signup", status_code=201)
def signup(body: SignupIn, request: Request, db: Session = Depends(get_db)):
    if not body.accept_terms:
        raise HTTPException(422, "Accept the Terms of Service, Privacy Policy and Data Processing Agreement")
    email = str(body.email).lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "An account with this email already exists")
    probs = password_problems(body.password, email=email)
    if probs:
        raise HTTPException(422, "Password must have " + ", ".join(probs))
    plan = db.query(Plan).filter_by(code="sandbox" if body.sandbox else settings.TRIAL_PLAN).first() or db.query(Plan).first()
    c = body.country.upper()
    org = Organization(name=body.organization.strip(), slug=slugify(body.organization, db), country=c, region=region_for(c), plan_id=plan.id if plan else None,
                       status="active" if body.sandbox else "trial", trial_ends_at=None if body.sandbox else now() + timedelta(days=settings.TRIAL_DAYS),
                       currency=CURRENCY.get(c, "EUR" if c in EU and c != "GB" else "USD"), seats=3, is_sandbox=body.sandbox, settings={}, branding={})
    db.add(org); db.flush()
    u = User(org_id=org.id, email=email, full_name=body.full_name.strip(), role="org_admin", password_hash=hash_password(body.password), password_changed_at=now(),
             timezone="Asia/Kolkata" if c == "IN" else "UTC")
    db.add(u); db.flush()
    ip = audit.client_ip(request)
    for doc, ver in LEGAL_VERSIONS.items():
        db.add(LegalAcceptance(user_id=u.id, document=doc, version=ver, ip=ip))
    audit.admin_log(db, org.id, u, "org.created", org.slug, after={"region": org.region, "plan": plan.code if plan else None, "sandbox": body.sandbox}, req=request)
    send_verification(db, u, org)
    db.commit()
    return {"message": "Account created. Check your email to verify your address.", "org_id": org.id, "region": org.region,
            "email_mode": "smtp" if notify.smtp_configured() else "dev_outbox"}


@router.post("/verify-email/{token}")
def verify_email(token: str, db: Session = Depends(get_db)):
    t = use_token(db, "verify_email", token)
    u = db.get(User, t.user_id); u.email_verified = True
    db.commit()
    return {"message": "Email verified"}


@router.post("/resend-verification")
def resend_verification(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if p.user.email_verified:
        return {"message": "Already verified"}
    send_verification(db, p.user, p.org); db.commit()
    return {"message": "Verification email sent"}


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    totp: str | None = None


def start_session(db, u: User, request: Request, mfa_passed: bool) -> tuple[str, UserSession]:
    sid = secrets.token_urlsafe(24)
    s = UserSession(id=sid, user_id=u.id, expires_at=now() + timedelta(hours=settings.SESSION_ABSOLUTE_HOURS), ip=audit.client_ip(request),
                    user_agent=request.headers.get("user-agent", "")[:300], mfa_passed=mfa_passed)
    db.add(s)
    return create_access_token(u.id, sid), s


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = str(body.email).lower()
    u = db.query(User).filter_by(email=email).first()
    generic = HTTPException(401, "Incorrect email or password")
    if not u:
        verify_password(body.password, "$2b$12$" + "x" * 53)  # equalise timing
        raise generic
    if u.locked_until and u.locked_until > now():
        raise HTTPException(423, "Too many failed sign-ins. Try again later or reset your password.")
    org = db.get(Organization, u.org_id) if u.org_id else None
    if not verify_password(body.password, u.password_hash):
        u.failed_logins += 1
        if u.failed_logins >= settings.LOGIN_MAX_FAILURES:
            u.locked_until, u.failed_logins = now() + timedelta(minutes=settings.LOGIN_LOCK_MINUTES), 0
            notify.send_email(db, org=org, to=u.email, kind="security_alert", subject="VAICS Sign: account temporarily locked",
                              body=f"Your account was locked for {settings.LOGIN_LOCK_MINUTES} minutes after repeated failed sign-ins from IP {audit.client_ip(request)}. If this wasn't you, reset your password.")
        db.commit()
        raise generic
    if not u.is_active:
        raise HTTPException(403, "Account deactivated")
    ip = audit.client_ip(request)
    if u.last_login_ip and ip and u.last_login_ip != ip:
        notify.send_email(db, org=org, to=u.email, kind="security_alert", subject="New sign-in to VAICS Sign",
                          body=f"We noticed a sign-in from a new IP address ({ip}). If this wasn't you, reset your password and end other sessions.")
    must_mfa = u.mfa_enabled or (org and org_settings(org).get("mfa_required"))
    if u.mfa_enabled:
        if not body.totp:
            db.commit()
            return {"mfa_required": True}
        if not (verify_totp(u.mfa_secret, body.totp) or _use_recovery(u, body.totp)):
            u.failed_logins += 1; db.commit()
            raise HTTPException(401, "Invalid authentication code")
    u.failed_logins, u.locked_until, u.last_login_at, u.last_login_ip = 0, None, now(), ip
    token, s = start_session(db, u, request, mfa_passed=bool(u.mfa_enabled) or not must_mfa)
    db.commit()
    out = {"access_token": token, "token_type": "bearer", "user": user_out(u, org)}
    if must_mfa and not u.mfa_enabled:
        out["mfa_enrolment_required"] = True
    exp = (org_settings(org).get("password_policy") or {}).get("expiry_days") if org else 0
    if exp and u.password_changed_at and u.password_changed_at < now() - timedelta(days=int(exp)):
        out["password_expired"] = True
    return out


def _use_recovery(u: User, code: str) -> bool:
    h = sha256_hex(code.strip().replace("-", "").lower())
    if h in (u.mfa_recovery_hashes or []):
        u.mfa_recovery_hashes = [x for x in u.mfa_recovery_hashes if x != h]; return True
    return False


@router.get("/me")
def me(p: Principal = Depends(get_principal)):
    return user_out(p.user, p.org)


class ProfileIn(BaseModel):
    full_name: str | None = None
    title: str | None = None
    company: str | None = None
    language: str | None = None
    timezone: str | None = None
    notify_prefs: dict | None = None
    onboarding_done: bool | None = None


@router.patch("/me")
def update_me(body: ProfileIn, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p.user, k, v)
    db.commit()
    return user_out(p.user, p.org)


@router.post("/logout")
def logout(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if p.session:
        p.session.revoked = True; db.commit()
    return {"ok": True}


@router.get("/sessions")
def sessions(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    rows = db.query(UserSession).filter_by(user_id=p.user.id, revoked=False).filter(UserSession.expires_at > now()).order_by(UserSession.last_seen_at.desc()).all()
    return [{"id": s.id[:8], "created_at": s.created_at, "last_seen_at": s.last_seen_at, "ip": s.ip, "user_agent": s.user_agent, "current": p.session and s.id == p.session.id} for s in rows]


@router.delete("/sessions/{prefix}")
def end_session(prefix: str, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    n = 0
    for s in db.query(UserSession).filter_by(user_id=p.user.id, revoked=False):
        if prefix == "all-others" and (not p.session or s.id != p.session.id) or s.id.startswith(prefix) and len(prefix) >= 8:
            s.revoked = True; n += 1
    db.commit()
    return {"ended": n}


class ForgotIn(BaseModel):
    email: EmailStr


@router.post("/password/forgot")
def forgot(body: ForgotIn, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(email=str(body.email).lower()).first()
    if u and u.is_active:
        raw, _ = issue_token(db, "reset_password", minutes=settings.RESET_TOKEN_MINUTES, user_id=u.id)
        org = db.get(Organization, u.org_id) if u.org_id else None
        notify.send_email(db, org=org, to=u.email, kind="reset_password", subject="Reset your VAICS Sign password",
                          body=f"Use the link below to set a new password. It expires in {settings.RESET_TOKEN_MINUTES} minutes and can be used once.",
                          link=f"{settings.PUBLIC_APP_URL}/reset-password/{raw}")
        db.commit()
    return {"message": "If an account exists for that email, a reset link has been sent."}


class ResetIn(BaseModel):
    token: str
    password: str


def set_password(db, u: User, pw: str):
    org = db.get(Organization, u.org_id) if u.org_id else None
    pol = (org_settings(org).get("password_policy") or {}) if org else {}
    probs = password_problems(pw, pol, u.email)
    if probs:
        raise HTTPException(422, "Password must have " + ", ".join(probs))
    hist = int(pol.get("history", 3))
    for old in ([u.password_hash] + list(u.password_history or []))[:hist]:
        if old and verify_password(pw, old):
            raise HTTPException(422, f"Do not reuse any of your last {hist} passwords")
    u.password_history = ([u.password_hash] + list(u.password_history or []))[:hist] if u.password_hash else []
    u.password_hash, u.password_changed_at = hash_password(pw), now()


@router.post("/password/reset")
def reset(body: ResetIn, db: Session = Depends(get_db)):
    t = use_token(db, "reset_password", body.token)
    u = db.get(User, t.user_id)
    set_password(db, u, body.password)
    u.locked_until, u.failed_logins = None, 0
    for s in db.query(UserSession).filter_by(user_id=u.id): s.revoked = True
    db.commit()
    return {"message": "Password updated. Sign in with your new password."}


class ChangePwIn(BaseModel):
    current_password: str
    new_password: str


@router.post("/password/change")
def change_pw(body: ChangePwIn, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, p.user.password_hash):
        raise HTTPException(403, "Current password is incorrect")
    set_password(db, p.user, body.new_password)
    db.commit()
    return {"message": "Password changed"}


# ---- MFA (TOTP + recovery codes). Passkeys/SMS as second factor: not implemented (see FRS traceability) ----
@router.post("/mfa/setup")
def mfa_setup(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if p.user.mfa_enabled:
        raise HTTPException(409, "MFA already enabled")
    p.user.mfa_secret = new_totp_secret(); db.commit()
    return {"secret": p.user.mfa_secret, "otpauth_uri": totp_uri(p.user.mfa_secret, p.user.email, settings.BRAND_PRODUCT_NAME)}


class CodeIn(BaseModel):
    code: str


@router.post("/mfa/enable")
def mfa_enable(body: CodeIn, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if not p.user.mfa_secret or not verify_totp(p.user.mfa_secret, body.code):
        raise HTTPException(400, "Invalid code")
    codes = [secrets.token_hex(5) for _ in range(8)]
    p.user.mfa_enabled, p.user.mfa_recovery_hashes = True, [sha256_hex(c) for c in codes]
    if p.session: p.session.mfa_passed = True
    audit.admin_log(db, p.user.org_id, p.user, "user.mfa_enabled", p.user.email)
    db.commit()
    return {"enabled": True, "recovery_codes": codes}


@router.post("/mfa/disable")
def mfa_disable(body: CodeIn, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if p.org and org_settings(p.org).get("mfa_required"):
        raise HTTPException(403, "Your organization requires MFA")
    if not verify_totp(p.user.mfa_secret or "", body.code):
        raise HTTPException(400, "Invalid code")
    p.user.mfa_enabled, p.user.mfa_secret, p.user.mfa_recovery_hashes = False, None, []
    audit.admin_log(db, p.user.org_id, p.user, "user.mfa_disabled", p.user.email)
    db.commit()
    return {"enabled": False}


# ---- MFA enrolment for sessions created before enrolment when org enforces MFA ----
def mfa_pending_principal(request: Request, db: Session = Depends(get_db)):
    from ..core.security import decode_access_token
    h = request.headers.get("authorization", "")
    claims = decode_access_token(h[7:]) if h.lower().startswith("bearer ") else None
    s = db.get(UserSession, (claims or {}).get("sid", ""))
    if not s or s.revoked:
        raise HTTPException(401, "Not authenticated")
    return db.get(User, s.user_id), s


@router.post("/mfa/enrol-setup")
def enrol_setup(ctx=Depends(mfa_pending_principal), db: Session = Depends(get_db)):
    u, s = ctx
    if u.mfa_enabled: raise HTTPException(409, "MFA already enabled")
    u.mfa_secret = new_totp_secret(); db.commit()
    return {"secret": u.mfa_secret, "otpauth_uri": totp_uri(u.mfa_secret, u.email, settings.BRAND_PRODUCT_NAME)}


@router.post("/mfa/enrol-enable")
def enrol_enable(body: CodeIn, ctx=Depends(mfa_pending_principal), db: Session = Depends(get_db)):
    u, s = ctx
    if not u.mfa_secret or not verify_totp(u.mfa_secret, body.code):
        raise HTTPException(400, "Invalid code")
    codes = [secrets.token_hex(5) for _ in range(8)]
    u.mfa_enabled, u.mfa_recovery_hashes, s.mfa_passed = True, [sha256_hex(c) for c in codes], True
    db.commit()
    return {"enabled": True, "recovery_codes": codes}


# ---- invitations ----
@router.get("/invitations/{token}")
def invitation_info(token: str, db: Session = Depends(get_db)):
    t = db.query(OneTimeToken).filter_by(kind="invite", token_hash=sha256_hex(token)).first()
    if not t or t.revoked or t.used_at or t.expires_at < now():
        raise HTTPException(400, "This invitation is invalid or has expired")
    org = db.get(Organization, t.org_id)
    return {"email": t.email, "organization": org.name, "role": t.data.get("role")}


class AcceptIn(BaseModel):
    token: str
    full_name: str
    password: str
    accept_terms: bool


@router.post("/invitations/accept")
def accept_invite(body: AcceptIn, request: Request, db: Session = Depends(get_db)):
    if not body.accept_terms: raise HTTPException(422, "Accept the terms to continue")
    t = use_token(db, "invite", body.token)
    inv = db.query(Invitation).filter_by(token_id=t.id).first()
    if not inv or inv.status != "pending": raise HTTPException(400, "Invitation no longer valid")
    if db.query(User).filter_by(email=t.email).first(): raise HTTPException(409, "An account with this email already exists")
    org = db.get(Organization, t.org_id)
    if db.query(User).filter_by(org_id=org.id, is_active=True).count() >= org.seats:
        raise HTTPException(402, {"code": "seats_exhausted", "message": "No free seats. Ask your admin to add seats."})
    u = User(org_id=org.id, email=t.email, full_name=body.full_name.strip(), role=inv.role, email_verified=True)
    db.add(u); db.flush()
    set_password(db, u, body.password)
    for doc, ver in LEGAL_VERSIONS.items():
        db.add(LegalAcceptance(user_id=u.id, document=doc, version=ver, ip=audit.client_ip(request)))
    inv.status = "accepted"
    audit.admin_log(db, org.id, u, "user.joined", u.email, after={"role": u.role}, req=request)
    db.commit()
    return {"message": "Welcome! You can now sign in."}


@router.get("/social/{provider}")
def social(provider: str):
    raise HTTPException(501, f"Sign-in with {provider} is not configured on this server (OIDC client not set up).")
