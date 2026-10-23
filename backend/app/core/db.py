from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

kw = {"connect_args": {"check_same_thread": False}} if settings.is_sqlite else {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}
engine = create_engine(settings.DATABASE_URL, **kw)
if settings.is_sqlite:
    @event.listens_for(engine, "connect")
    def _fk(dbapi_con, _):
        dbapi_con.execute("PRAGMA foreign_keys=ON")
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
