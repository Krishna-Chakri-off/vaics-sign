from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routers import auth, sign  # CMS routers (changes, misc) unmounted: VAICS Sign only
from . import sign_models  # noqa: F401  (register tables)
from .database import Base, engine

app = FastAPI(title=settings.APP_NAME, version="1.0.0", docs_url="/docs")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
                   allow_origin_regex=settings.CORS_ORIGIN_REGEX, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
Base.metadata.create_all(engine)  # creates new sign_* tables if missing
sign_models.ensure_columns(engine)
for r in (auth.router, sign.router):
    app.include_router(r, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}
