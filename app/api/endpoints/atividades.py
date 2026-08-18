"""
Endpoints CRUD para Atividades.

Rotas:
    POST  /api/atividades          → Criar atividade
    GET   /api/atividades          → Listar atividades
    GET   /api/atividades/{uuid}   → Detalhe de atividade (com funções)
    PATCH /api/atividades/{uuid}   → Atualizar atividade (campos + status)
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_db
from app.db.models import Atividade
from app.schemas.atividade import AtividadeCreate, AtividadeUpdate, AtividadeResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/atividades", tags=["Atividades"])


@router.post("", response_model=AtividadeResponse, status_code=201)
async def criar_atividade(
    body: AtividadeCreate,
    session: AsyncSession = Depends(get_db),
):
    """Cadastra uma nova atividade (lista de exercícios)."""
    atividade = Atividade(
        titulo=body.titulo,
        descricao=body.descricao,
        pontuacao_maxima=body.pontuacao_maxima,
        data_abertura=body.data_abertura,
        data_fechamento=body.data_fechamento,
        status=body.status,
        tipo=body.tipo,
        duracao_minutos=body.duracao_minutos,
        bloquear_paste=body.bloquear_paste,
        notas_liberadas=body.notas_liberadas,
    )
    session.add(atividade)
    await session.flush()
    await session.refresh(atividade)

    logger.info("Atividade criada: %s (uuid=%s)", atividade.titulo, atividade.uuid)
    return AtividadeResponse.model_validate(atividade)


@router.get("", response_model=list[AtividadeResponse])
async def listar_atividades(session: AsyncSession = Depends(get_db)):
    """Lista todas as atividades."""
    result = await session.execute(
        select(Atividade)
        .options(selectinload(Atividade.funcoes))
        .order_by(Atividade.created_at.desc())
    )
    atividades = result.scalars().all()
    return [AtividadeResponse.model_validate(a) for a in atividades]


@router.get("/{atividade_uuid}")
async def detalhe_atividade(
    atividade_uuid: str,
    session: AsyncSession = Depends(get_db),
):
    """Retorna detalhes de uma atividade com suas funções."""
    result = await session.execute(
        select(Atividade)
        .options(selectinload(Atividade.funcoes))
        .where(Atividade.uuid == atividade_uuid)
    )
    atividade = result.scalar_one_or_none()

    if not atividade:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")

    return AtividadeResponse.model_validate(atividade)


# Transições de status válidas
TRANSICOES_VALIDAS = {
    ("rascunho", "publicado"),
    ("rascunho", "fechado"),
    ("publicado", "fechado"),
    ("fechado", "publicado"),
}


@router.patch("/{atividade_uuid}", response_model=AtividadeResponse)
async def atualizar_atividade(
    atividade_uuid: str,
    body: AtividadeUpdate,
    session: AsyncSession = Depends(get_db),
):
    """
    Atualiza campos e/ou status de uma atividade.

    Regras de transição de status:
      - rascunho → publicado  (requer ≥1 função com casos de teste)
      - rascunho → fechado    (cancelar sem publicar)
      - publicado → fechado   (encerrar)
      - fechado → publicado   (reabrir)
      - publicado/fechado → rascunho  ❌ BLOQUEADO
    """
    result = await session.execute(
        select(Atividade)
        .options(selectinload(Atividade.funcoes))
        .where(Atividade.uuid == atividade_uuid)
    )
    atividade = result.scalar_one_or_none()

    if not atividade:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")

    update_data = body.model_dump(exclude_unset=True)

    # ── Validar transição de status ──────────────────────────────
    novo_status = update_data.get("status")
    if novo_status and novo_status != atividade.status:
        par = (atividade.status, novo_status)
        if par not in TRANSICOES_VALIDAS:
            raise HTTPException(
                status_code=400,
                detail=f"Transição de status inválida: {atividade.status} → {novo_status}",
            )

        # Para publicar, exigir pelo menos 1 função
        if novo_status == "publicado" and not atividade.funcoes:
            raise HTTPException(
                status_code=400,
                detail="Não é possível publicar: a atividade precisa ter pelo menos 1 função cadastrada.",
            )

        # Auto-set dataAbertura ao publicar
        if novo_status == "publicado" and not atividade.data_abertura:
            atividade.data_abertura = datetime.now(timezone.utc)

    # ── Aplicar campos editáveis ─────────────────────────────────
    for campo in ("titulo", "descricao", "pontuacao_maxima", "data_abertura", "data_fechamento", "status", "tipo", "duracao_minutos", "bloquear_paste", "notas_liberadas"):
        if campo in update_data:
            setattr(atividade, campo, update_data[campo])

    await session.flush()
    await session.refresh(atividade)

    logger.info("Atividade atualizada: %s (uuid=%s, status=%s)", atividade.titulo, atividade.uuid, atividade.status)
    return AtividadeResponse.model_validate(atividade)
