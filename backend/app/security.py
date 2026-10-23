import hashlib
from datetime import datetime, timedelta, timezone
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from . import models

ALGO = "HS256"
bearer = HTTPBearer(auto_error=False)


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except ValueError:
        return False


def create_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.SECRET_KEY, algorithm=ALGO)


def sha(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def get_current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> models.User:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    token = cred.credentials
    user = None
    if token.startswith("cms_"):  # API token for CI/CD pipelines
        t = db.query(models.ApiToken).filter_by(token_hash=sha(token)).first()
        if t:
            t.last_used_at = models.now()
            db.commit()
            user = db.get(models.User, t.user_id)
    else:
        try:
            uid = int(jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])["sub"])
            user = db.get(models.User, uid)
        except (JWTError, KeyError, ValueError):
            user = None
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return user


def require_roles(*roles):
    def dep(user: models.User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user
    return dep
