from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.core.config import settings
from app.core.db import Base
from app import models  # noqa: F401

config = context.config
if config.config_file_name: fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = Base.metadata


def run_offline():
    context.configure(url=settings.DATABASE_URL, target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction(): context.run_migrations()


def run_online():
    eng = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with eng.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=conn.dialect.name == "sqlite", compare_type=True)
        with context.begin_transaction(): context.run_migrations()


run_offline() if context.is_offline_mode() else run_online()
