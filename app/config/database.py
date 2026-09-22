"""Conexão assíncrona sob demanda, sem migração ou commit implícitos."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .settings import Settings


def make_engine(settings: Settings) -> AsyncEngine:
    """Constrói engine; o PostgreSQL só é acessado quando a sessão executar SQL."""
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
    )


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Dependência FastAPI: serviço faz commit explícito; transações abertas sofrem rollback."""
    app_state = request.app.state
    if app_state.session_factory is None:
        # Inicialização síncrona, antes do primeiro await, sem abrir conexão.
        engine = make_engine(app_state.settings)
        app_state.db_engine = engine
        app_state.session_factory = make_session_factory(engine)

    async with app_state.session_factory() as session:
        try:
            yield session
        finally:
            if session.in_transaction():
                await session.rollback()


async def dispose_db_engine(app) -> None:
    """Libera pool ao desligar; aplicações sem acesso a DB não criam engine."""
    engine = app.state.db_engine
    if engine is not None:
        try:
            await engine.dispose()
        finally:
            app.state.db_engine = None
            app.state.session_factory = None
