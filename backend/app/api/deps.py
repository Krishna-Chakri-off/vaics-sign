from dataclasses import dataclass, field
from datetime import timedelta
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.orm import Session
from ..core.config import settings
from ..core.db import get_db
from ..core.permissions import has_perm
from ..core.security import decode_access_token, sha256_hex
from ..models import User, Organization, UserSession, ApiKey, Envelope, Group, now
from ..services import usage

bearer = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass
class Principal:
    user: User
    org: Organization | None
    via: str = "session"  # session | api_key
    scopes: list = field(default_factory=list)
    session: UserSession | None = None

    def can(self, perm: str) -> bool:
        return has_perm(self.user.role, perm)


def _from_api_key(db, raw: str) -> Principal:
    k = db.query(ApiKey).filter_by(key_hash=sha256_hex(raw), revoked=False).first()
    if not k:
        raise HTTPException(401, "Invalid API key")
    user = db.get(User, k.user_id); org = db.get(Organization, k.org_id)
    if not user or not user.is_active or user.org_id != org.id:
        raise HTTPException(401, "API key owner is inactive")
    usage.require_feature(org, "api", "API access")
    k.last_used_at = now()
    usage.check_and_record(db, org, "api_calls")
    db.commit()
    return Principal(user=user, org=org, via="api_key", scopes=list(k.scopes or []))


def get_principal(request: Request, cred: HTTPAuthorizationCredentials | None = Depends(bearer), xkey: str | None = Depends(api_key_header),
                  db: Session = Depends(get_db)) -> Principal:
    raw = xkey or (cred.credentials if cred and cred.credentials.startswith("vsk_") else None)
    if raw:
        p = _from_api_key(db, raw)
    else:
        if not cred:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
        claims = decode_access_token(cred.credentials)
        if not claims:
            raise HTTPException(401, "Invalid or expired token")
        s = db.get(UserSession, claims.get("sid", ""))
        user = db.get(User, int(claims["sub"]))
        if not s or s.revoked or s.user_id != (user.id if user else None) or s.expires_at < now():
            raise HTTPException(401, "Session ended. Sign in again.")
        org = db.get(Organization, user.org_id) if user and user.org_id else None
        idle = int(((org.settings or {}).get("session_idle_minutes") if org else None) or settings.SESSION_IDLE_MINUTES)
        if s.last_seen_at < now() - timedelta(minutes=idle):
            s.revoked = True; db.commit()
            raise HTTPException(401, "Session timed out after inactivity. Sign in again.")
        if not s.mfa_passed:
            raise HTTPException(401, {"code": "mfa_required", "message": "Complete multi-factor authentication"})
        if not user or not user.is_active:
            raise HTTPException(401, "Account inactive")
        s.last_seen_at = now(); db.commit()
        p = Principal(user=user, org=org, session=s)
    if p.org and p.org.status == "suspended" and not request.url.path.startswith("/api/v1/auth"):
        raise HTTPException(403, {"code": "org_suspended", "message": f"Organization suspended: {p.org.suspended_reason or 'contact support'}"})
    if p.org and p.org.status == "closed" and request.method not in ("GET", "HEAD"):
        raise HTTPException(403, {"code": "org_closed", "message": "Organization is closed; data is read-only"})
    return p


def org_member(p: Principal = Depends(get_principal)) -> Principal:
    if not p.org:
        raise HTTPException(403, "This action requires an organization account")
    return p


def perm(name: str, scope: str | None = None):
    def dep(p: Principal = Depends(org_member)) -> Principal:
        if not p.can(name):
            raise HTTPException(403, f"Permission required: {name}")
        if p.via == "api_key" and scope and scope not in p.scopes:
            raise HTTPException(403, f"API key scope required: {scope}")
        return p
    return dep


def scope(name: str):
    def dep(p: Principal = Depends(org_member)) -> Principal:
        if p.via == "api_key" and name not in p.scopes:
            raise HTTPException(403, f"API key scope required: {name}")
        return p
    return dep


def platform_admin(p: Principal = Depends(get_principal)) -> Principal:
    if p.user.role != "platform_admin" or p.via != "session":
        raise HTTPException(403, "Platform administrators only")
    return p


def user_groups(db, p: Principal) -> list[int]:
    return [g.id for g in db.query(Group).filter_by(org_id=p.org.id).all() if p.user.id in (g.member_ids or [])]


def envelope_access(db, p: Principal, env_id: int, write: bool = False) -> Envelope:
    """Server-side tenant + ownership check (SEC-04). Platform staff never pass (no org)."""
    env = db.get(Envelope, env_id)
    if not env or env.org_id != p.org.id or env.deleted_at:
        raise HTTPException(404, "Envelope not found")
    if env.owner_id == p.user.id:
        return env
    if write:
        if p.user.role == "org_admin":
            return env
        raise HTTPException(403, "Only the sender or an org admin can change this envelope")
    if p.can("envelopes.view_all"):
        return env
    if env.visibility == "group" and env.group_id in user_groups(db, p):
        return env
    if any(r.host_user_id == p.user.id for r in env.recipients):
        return env
    raise HTTPException(403, "You do not have access to this envelope")
