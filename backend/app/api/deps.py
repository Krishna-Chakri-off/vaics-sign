from dataclasses import dataclass
from datetime import timedelta
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from ..core.config import settings
from ..core.db import get_db
from ..core.permissions import has_perm
from ..core.security import decode_access_token
from ..models import User, Organization, UserSession, Envelope, Group, now

bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    user: User
    org: Organization | None
    session: UserSession | None = None

    def can(self, perm: str) -> bool:
        return has_perm(self.user.role, perm)


def get_principal(request: Request, cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> Principal:
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


def perm(name: str):
    def dep(p: Principal = Depends(org_member)) -> Principal:
        if not p.can(name):
            raise HTTPException(403, f"Permission required: {name}")
        return p
    return dep


def user_groups(db, p: Principal) -> list[int]:
    return [g.id for g in db.query(Group).filter_by(org_id=p.org.id).all() if p.user.id in (g.member_ids or [])]


def envelope_access(db, p: Principal, env_id: int, write: bool = False) -> Envelope:
    """Server-side tenant + ownership check (SEC-04)."""
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
