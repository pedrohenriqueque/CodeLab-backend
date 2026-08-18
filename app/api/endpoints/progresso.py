"""
Endpoint de Progresso — Acompanhamento do aluno.

Rotas:
    GET /api/aluno/progresso  → Retorna melhor nota por função para um aluno
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.dependencies import get_db
from app.db.models import Submissao
from pydantic import BaseModel
from app.schemas.common import CAMEL_CONFIG

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/aluno/progresso", tags=["Progresso"])


class ProgressoFuncao(BaseModel):
    model_config = CAMEL_CONFIG
    funcao_uuid: str
    melhor_nota: float
    tentativas_usadas: int


class ProgressoResponse(BaseModel):
    model_config = CAMEL_CONFIG
    aluno_uuid: str
    progresso: list[ProgressoFuncao]


@router.get("", response_model=ProgressoResponse)
async def obter_progresso(
    aluno_uuid: str = Query(..., alias="alunoUuid", description="UUID do aluno"),
    session: AsyncSession = Depends(get_db),
):
    """
    Retorna a melhor nota e total de tentativas de cada função para um dado aluno.
    """
    # Agrupa submissões do aluno por função, pegando a maior nota e a contagem
    query = (
        select(
            Submissao.funcao_uuid,
            func.max(Submissao.nota).label("melhor_nota"),
            func.count(Submissao.uuid).label("tentativas_usadas")
        )
        .where(Submissao.aluno_uuid == aluno_uuid)
        .group_by(Submissao.funcao_uuid)
    )

    result = await session.execute(query)
    linhas = result.all()

    progresso_list = []
    for linha in linhas:
        progresso_list.append(
            ProgressoFuncao(
                funcao_uuid=linha.funcao_uuid,
                melhor_nota=float(linha.melhor_nota) if linha.melhor_nota is not None else 0.0,
                tentativas_usadas=linha.tentativas_usadas
            )
        )

    return ProgressoResponse(aluno_uuid=aluno_uuid, progresso=progresso_list)
