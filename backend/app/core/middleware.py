"""Security headers + in-process rate limiting (per IP for public/auth routes, per org for API keys).
For multi-instance production put a shared limiter (Redis) / WAF in front – this limiter is per process."""
import time
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from .config import settings

CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
       "font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        h = resp.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            h.setdefault("Content-Security-Policy", CSP)
            h.setdefault("X-Frame-Options", "DENY")
        if settings.ENV == "production":
            h.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
        return resp


class _Window:
    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)

    def hit(self, key: str, limit: int, per: float = 60.0):
        t = time.monotonic(); q = self.hits[key]
        while q and q[0] <= t - per: q.popleft()
        if len(q) >= limit:
            return False, 0, int(per - (t - q[0])) + 1
        q.append(t)
        return True, limit - len(q), int(per)


limiter = _Window()


def plan_api_limit(org) -> int:
    try:
        return int((org.plan.limits or {}).get("api_calls_per_min", 60))
    except Exception:
        return 60


class RateLimit(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
        path = request.url.path
        ip = request.client.host if request.client else "?"
        rule = None
        if path.startswith("/api/v1/auth/") or path.endswith(("/unlock", "/otp", "/verify-email")):
            rule = (f"auth:{ip}", settings.RATE_LIMIT_AUTH_PER_MIN)
        elif path.startswith(("/api/v1/public/", "/api/v1/verify")):
            rule = (f"pub:{ip}", settings.RATE_LIMIT_PUBLIC_PER_MIN)
        key = request.headers.get("x-api-key") or ""
        auth = request.headers.get("authorization", "")
        if not key and auth.lower().startswith("bearer vsk_"):
            key = auth[7:]
        if key:
            from .db import SessionLocal
            from ..models import ApiKey, Organization
            from .security import sha256_hex
            with SessionLocal() as db:
                k = db.query(ApiKey).filter_by(key_hash=sha256_hex(key), revoked=False).first()
                if k:
                    org = db.get(Organization, k.org_id)
                    rule = (f"org:{k.org_id}", plan_api_limit(org))
        if not rule:
            return await call_next(request)
        ok, remaining, reset = limiter.hit(*rule)
        if not ok:
            return JSONResponse({"detail": "Rate limit exceeded. Try again later."}, status_code=429,
                                headers={"Retry-After": str(reset), "X-RateLimit-Limit": str(rule[1]), "X-RateLimit-Remaining": "0"})
        resp = await call_next(request)
        resp.headers["X-RateLimit-Limit"] = str(rule[1]); resp.headers["X-RateLimit-Remaining"] = str(remaining); resp.headers["X-RateLimit-Reset"] = str(reset)
        return resp
