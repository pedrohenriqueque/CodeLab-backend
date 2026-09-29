"""Entrypoint ASGI isolado: carregamento da configuração na primeira chamada ASGI."""

from functools import lru_cache
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.middleware.cors import CORSMiddleware

from .config.settings import Settings, get_settings
from .config.database import dispose_db_engine
from .core.exceptions import (
    CodelabException,
    codelab_exception_handler,
    http_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)
from .routes.health import router as health_router
from .routes.auth import router as auth_router
from .routes.admin import router as admin_router
from .routes.classes import router as classes_router
from .routes.functions import router as functions_router
from .routes.test_cases import router as test_cases_router
from .routes.activities import router as activities_router
from .routes.submissions import router as submissions_router
from .routes.progress import router as progress_router
from .routes.sandbox import router as sandbox_router
import asyncio
from datetime import datetime, timezone
from sqlalchemy import update
from .models.atividade import Atividade
from .config.database import dispose_db_engine, make_engine, make_session_factory

from .routes.dashboard import router as dashboard_router

async def job_fechar_atividades_expiradas(app: FastAPI):
    """Job periódico em background que persiste o encerramento de atividades expiradas no banco."""
    while True:
        try:
            await asyncio.sleep(60)
            if app.state.session_factory is None:
                if app.state.db_engine is None:
                    app.state.db_engine = make_engine(app.state.settings)
                app.state.session_factory = make_session_factory(app.state.db_engine)

            async with app.state.session_factory() as session:
                agora = datetime.now(timezone.utc)
                stmt = (
                    update(Atividade)
                    .where(Atividade.status == "PUBLICADA", Atividade.fim_em <= agora)
                    .values(status="ENCERRADA")
                )
                res = await session.execute(stmt)
                if res.rowcount > 0:
                    await session.commit()
        except asyncio.CancelledError:
            break
        except Exception:
            pass

def create_app(settings: Settings | None = None) -> FastAPI:
    """Cria a aplicação sem conectar a banco, Judge0 ou executar DDL."""
    settings = settings if settings is not None else get_settings()
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        bg_task = asyncio.create_task(job_fechar_atividades_expiradas(app))
        try:
            yield
        finally:
            bg_task.cancel()
            try:
                await bg_task
            except asyncio.CancelledError:
                pass
            await dispose_db_engine(app)

    application = FastAPI(title="CodeLab API", version="2.0.0", lifespan=lifespan)
    application.state.settings = settings
    application.state.db_engine = None
    application.state.session_factory = None
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,  # JWT é enviado via Authorization, não cookie.
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.add_exception_handler(CodelabException, codelab_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(Exception, unexpected_exception_handler)

    application.include_router(health_router, prefix="/api")
    application.include_router(auth_router, prefix="/api")
    application.include_router(admin_router, prefix="/api")
    application.include_router(classes_router, prefix="/api")
    application.include_router(functions_router, prefix="/api")
    application.include_router(test_cases_router, prefix="/api")
    application.include_router(activities_router, prefix="/api")
    application.include_router(submissions_router, prefix="/api")
    application.include_router(progress_router, prefix="/api")
    application.include_router(sandbox_router, prefix="/api")
    application.include_router(dashboard_router, prefix="/api")
    return application


@lru_cache(maxsize=1)
def _runtime() -> FastAPI:
    # Não exigir .env só para importar o módulo; configuração inválida falha
    # explicitamente antes do primeiro request ou startup ASGI.
    return create_app()


class _LazyASGI:
    async def __call__(self, scope, receive, send):
        await _runtime()(scope, receive, send)


app = _LazyASGI()
