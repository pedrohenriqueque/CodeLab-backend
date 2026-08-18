"""
Endpoints CRUD para Funções e Casos de Teste.

Rotas:
    POST /api/funcoes                             → Criar função vinculada a atividade
    GET  /api/funcoes                             → Listar funções (filtro por atividade)
    GET  /api/funcoes/{uuid}                      → Detalhe de função (com casos de teste)

    POST /api/funcoes/{uuid}/casos-teste          → Cadastrar caso(s) de teste
    GET  /api/funcoes/{uuid}/casos-teste          → Listar casos de teste
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_db
from app.db.models import Funcao, CasoTeste, Atividade
from app.schemas.funcao import FuncaoCreate, FuncaoResponse, FuncaoDetailResponse
from app.schemas.caso_teste import CasoTesteCreate, CasoTesteResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/funcoes", tags=["Funções"])


# ---- FUNÇÕES ----

@router.post("", response_model=FuncaoResponse, status_code=201)
async def criar_funcao(
    body: FuncaoCreate,
    atividade_uuid: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    """
    Cadastra uma nova função C vinculada a uma atividade.

    Se atividade_uuid não for fornecido no query param, deve vir no body.
    """
    # Resolver atividade_uuid
    atv_uuid = atividade_uuid
    if not atv_uuid:
        # Sem atividade especificada: pegar a primeira ou criar uma default
        result = await session.execute(select(Atividade).limit(1))
        atividade = result.scalar_one_or_none()
        if not atividade:
            # Criar atividade default
            atividade = Atividade(titulo="Atividade Padrão", status="rascunho")
            session.add(atividade)
            await session.flush()
            logger.info("Atividade default criada: %s", atividade.uuid)
        atv_uuid = atividade.uuid
    else:
        # Verificar se atividade existe
        result = await session.execute(
            select(Atividade).where(Atividade.uuid == atv_uuid)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Atividade não encontrada")

    funcao = Funcao(
        atividade_uuid=atv_uuid,
        nome_funcao=body.nome_funcao,
        pontos=body.pontos,
        ordem=body.ordem,
        parametros=[p.model_dump() for p in body.parametros],
        retorno=body.retorno.model_dump(),
        descricao=body.descricao,
    )
    session.add(funcao)
    await session.flush()
    await session.refresh(funcao)

    logger.info("Funcao criada: %s (uuid=%s)", funcao.nome_funcao, funcao.uuid)
    return FuncaoResponse.model_validate(funcao)


@router.get("", response_model=list[FuncaoResponse])
async def listar_funcoes(
    atividade_uuid: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    """Lista funções, opcionalmente filtradas por atividade."""
    query = select(Funcao)
    if atividade_uuid:
        query = query.where(Funcao.atividade_uuid == atividade_uuid)
    query = query.order_by(Funcao.ordem.asc(), Funcao.created_at.asc())

    result = await session.execute(query)
    funcoes = result.scalars().all()
    return [FuncaoResponse.model_validate(f) for f in funcoes]


@router.get("/{funcao_uuid}")
async def detalhe_funcao(
    funcao_uuid: str,
    session: AsyncSession = Depends(get_db),
):
    """Retorna detalhes de uma função com seus casos de teste."""
    result = await session.execute(
        select(Funcao)
        .options(selectinload(Funcao.casos_teste))
        .where(Funcao.uuid == funcao_uuid)
    )
    funcao = result.scalar_one_or_none()

    if not funcao:
        raise HTTPException(status_code=404, detail="Função não encontrada")

    return FuncaoDetailResponse.model_validate(funcao)


# ---- CASOS DE TESTE ----

@router.post("/{funcao_uuid}/casos-teste", status_code=201)
async def criar_casos_teste(
    funcao_uuid: str,
    body: CasoTesteCreate | list[CasoTesteCreate],
    session: AsyncSession = Depends(get_db),
):
    """
    Cadastra caso(s) de teste para uma função.
    Aceita um objeto ou uma lista.
    """
    # Verificar função
    result = await session.execute(
        select(Funcao).where(Funcao.uuid == funcao_uuid)
    )
    funcao = result.scalar_one_or_none()
    if not funcao:
        raise HTTPException(status_code=404, detail="Função não encontrada")

    # Normalizar
    items = body if isinstance(body, list) else [body]

    # Próximo número
    result = await session.execute(
        select(func.coalesce(func.max(CasoTeste.numero), 0))
        .where(CasoTeste.funcao_uuid == funcao_uuid)
    )
    proximo_numero = result.scalar() + 1

    criados = []
    for item in items:
        caso = CasoTeste(
            funcao_uuid=funcao_uuid,
            numero=proximo_numero,
            inputs=item.inputs,
            output_esperado=item.output_esperado,
            descricao=item.descricao,
        )
        session.add(caso)
        criados.append(caso)
        proximo_numero += 1

    await session.flush()
    for c in criados:
        await session.refresh(c)

    logger.info("%d caso(s) criados para funcao %s", len(criados), funcao.nome_funcao)

    result_list = [CasoTesteResponse.model_validate(c) for c in criados]
    return result_list if len(result_list) > 1 else result_list[0]


@router.get("/{funcao_uuid}/casos-teste", response_model=list[CasoTesteResponse])
async def listar_casos_teste(
    funcao_uuid: str,
    session: AsyncSession = Depends(get_db),
):
    """Lista todos os casos de teste de uma função."""
    result = await session.execute(
        select(Funcao).where(Funcao.uuid == funcao_uuid)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Função não encontrada")

    result = await session.execute(
        select(CasoTeste)
        .where(CasoTeste.funcao_uuid == funcao_uuid)
        .order_by(CasoTeste.numero.asc())
    )
    casos = result.scalars().all()
    return [CasoTesteResponse.model_validate(c) for c in casos]
