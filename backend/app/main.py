"""VAICS Sign – internal e-signature service for VAICS."""
import logging
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .core.db import Base, engine
from .core.middleware import SecurityHeaders, RateLimit
from .api import auth, envelopes, signing, admin, templates, reports, verify, privacy

logging.basicConfig(level=logging.INFO)
TAGS = [{"name": n} for n in ("auth", "envelopes", "templates & bulk send", "signing (public)", "public verification", "organization admin",
                                "reports", "privacy")]
app = FastAPI(title="VAICS Sign API", version="1.0.0", openapi_tags=TAGS, docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/v1/openapi.json",
              description="VAICS Sign internal e-signature service. Authenticate with `Authorization: Bearer <JWT>`.")
app.add_middleware(RateLimit)
app.add_middleware(SecurityHeaders)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
                   allow_origin_regex=settings.CORS_ORIGIN_REGEX if settings.ENV != "production" else None,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["Content-Disposition", "X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"])

v1 = APIRouter(prefix="/api/v1")
for m in (auth, envelopes, signing, admin, templates, reports, verify, privacy):
    v1.include_router(m.router)
app.include_router(v1)


@app.get("/api/health", tags=["public verification"])
def health():
    return {"status": "ok", "service": "vaics-sign", "version": app.version}


@app.on_event("startup")
def startup():
    if settings.ENV == "production" and (settings.SECRET_KEY.startswith("dev-") or len(settings.SECRET_KEY) < 32):
        raise RuntimeError("Set a strong SECRET_KEY (>= 32 chars) in production")
    from . import models  # noqa: F401
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
    if settings.RUN_SCHEDULER:
        from .services.jobs import start_scheduler
        start_scheduler()
