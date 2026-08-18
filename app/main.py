"""
CodeLab — Ponto de entrada FastAPI.

Plataforma de avaliação automática de exercícios de programação em C.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import CodelabException, codelab_exception_handler
from app.db.session import init_db

# Importar routers
from app.api.endpoints.auth import router as auth_router
from app.api.endpoints.atividades import router as atividades_router
from app.api.endpoints.funcoes import router as funcoes_router
from app.api.endpoints.submissoes import router as submissoes_router
from app.api.endpoints.progresso import router as progresso_router
from app.api.endpoints.dashboard import router as dashboard_router
from app.api.endpoints.sandbox import router as sandbox_router
# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Executa na inicialização e finalização da aplicação."""
    # Startup
    logger.info("Inicializando CodeLab Backend...")
    await init_db()
    logger.info("Database inicializado")
    logger.info("Swagger UI disponivel em: http://localhost:8000/docs")
    yield
    # Shutdown
    logger.info("Encerrando CodeLab Backend...")


app = FastAPI(
    title="CodeLab API",
    description="Plataforma de avaliação automática de exercícios de programação em C",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(CodelabException, codelab_exception_handler)

# Routers
app.include_router(auth_router)
app.include_router(atividades_router)
app.include_router(funcoes_router)
app.include_router(submissoes_router)
app.include_router(progresso_router)
app.include_router(dashboard_router)
app.include_router(sandbox_router)


# Health check
@app.get("/api/health", tags=["Health"])
async def health():
    return {"status": "ok"}


# Exemplo de uso
@app.get("/api/exemplo", tags=["Exemplo"])
async def exemplo():
    """Retorna um exemplo completo do fluxo de uso."""
    return {
        "descricao": "Fluxo: criar atividade → criar funcao → adicionar casos de teste → submeter codigo",
        "passo1_criar_atividade": {
            "method": "POST",
            "url": "/api/atividades",
            "body": {
                "titulo": "Lista 1 - Funções Básicas",
                "pontuacaoMaxima": 100,
            },
        },
        "passo2_criar_funcao": {
            "method": "POST",
            "url": "/api/funcoes?atividade_uuid=<UUID_DA_ATIVIDADE>",
            "body": {
                "nomeFuncao": "fatorial",
                "pontos": 10,
                "parametros": [{"nome": "n", "tipo": "int"}],
                "retorno": {"tipo": "int"},
                "descricao": "Calcula o fatorial de n",
            },
        },
        "passo3_criar_casos_teste": {
            "method": "POST",
            "url": "/api/funcoes/<UUID_DA_FUNCAO>/casos-teste",
            "body": [
                {"inputs": {"n": 0}, "outputEsperado": {"valor": 1}, "descricao": "0! = 1"},
                {"inputs": {"n": 5}, "outputEsperado": {"valor": 120}, "descricao": "5! = 120"},
            ],
        },
        "passo4_submeter_codigo": {
            "method": "POST",
            "url": "/api/submissoes",
            "body": {
                "funcaoUuid": "<UUID_DA_FUNCAO>",
                "codigo": "int fatorial(int n) { if (n <= 1) return 1; return n * fatorial(n - 1); }",
            },
        },
    }
