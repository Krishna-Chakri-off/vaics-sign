from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

kw = {"connect_args": {"check_same_thread": False}} if settings.DATABASE_URL.startswith("sqlite") else {"pool_pre_ping": True}
engine = create_engine(settings.DATABASE_URL, **kw)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
