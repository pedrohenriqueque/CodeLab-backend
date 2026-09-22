"""Migrations explícitas do backend_v2, nunca executadas no startup."""

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend_v2.app.config.settings import Settings, get_settings
from backend_v2.app.models import Base

config = context.config
target_metadata = Base.metadata


def migration_settings() -> Settings:
    # Permite fixtures injetarem Settings sintéticas sem ler .env real.
    return config.attributes.get("settings") or get_settings()


def run_migrations_offline() -> None:
    url = migration_settings().database_url.get_secret_value()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    url = migration_settings().database_url.get_secret_value()
    engine = async_engine_from_config(
        {"sqlalchemy.url": url}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
