"""
Endpoints CRUD para Funções e Casos de Teste (Biblioteca de Funções).

Rotas:
    POST   /api/funcoes                             → Criar função na biblioteca
    GET    /api/funcoes                             → Listar funções (busca, dificuldade, ou filtro por atividade)
    GET    /api/funcoes/{uuid}                      → Detalhe da função (com casos canônicos)
    PUT    /api/funcoes/{uuid}                      → Atualizar função na biblioteca
    DELETE /api/funcoes/{uuid}                      → Remover função da biblioteca (bloqueado se associada)

    POST   /api/funcoes/{uuid}/casos-teste          → Cadastrar caso(s) de teste canônico(s)
    GET    /api/funcoes/{uuid}/casos-teste          → Listar casos de teste canônicos
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_db, get_current_user
from app.db.models import Funcao, CasoTeste, Atividade, AtividadeFuncao, AtividadeFuncaoCasoTeste, Usuario
from app.schemas.funcao import FuncaoCreate, FuncaoUpdate, FuncaoResponse, FuncaoDetailResponse
from app.schemas.caso_teste import CasoTesteCreate, CasoTesteUpdate, CasoTesteResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/funcoes", tags=["Funções"])


# ---- FUNÇÕES (BIBLIOTECA) ----

@router.post("", response_model=FuncaoResponse, status_code=201)
async def criar_funcao(
    body: FuncaoCreate,
    atividade_uuid: str | None = Query(default=None),
    atividadeUuid: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
):
    """
    Cadastra uma nova função C na biblioteca de funções.
    
    Se atividade_uuid for fornecido, também cria a associação contextual AtividadeFuncao.
    """
    dif_padrao = body.dificuldade_padrao or body.dificuldade or "medio"

    funcao = Funcao(
        nome_funcao=body.nome_funcao,
        dificuldade_padrao=dif_padrao,
        parametros=[p.model_dump() for p in body.parametros],
        retorno=body.retorno.model_dump(),
        descricao=body.descricao,
        max_tentativas=body.max_tentativas,
        dicas=body.dicas,
    )
    session.add(funcao)
    await session.flush()

    atv_uuid = atividade_uuid or atividadeUuid
    if atv_uuid:
        # Verificar se a atividade informada existe
        res_atv = await session.execute(
            select(Atividade).where(Atividade.uuid == atv_uuid)
        )
        if not res_atv.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Atividade informada não encontrada"
            )

        af = AtividadeFuncao(
            atividade_uuid=atv_uuid,
            funcao_uuid=funcao.uuid,
            dificuldade=body.dificuldade or dif_padrao,
            peso=body.pontos if body.pontos is not None else 10.0,
            ordem=body.ordem if body.ordem is not None else 0,
        )
        session.add(af)
        await session.flush()

    await session.refresh(funcao)
    logger.info("Funcao criada na biblioteca: %s (uuid=%s)", funcao.nome_funcao, funcao.uuid)

    resp = FuncaoResponse.model_validate(funcao)
    if atv_uuid:
        resp.atividade_uuid = atv_uuid
        resp.pontos = float(body.pontos or 10.0)
        resp.ordem = body.ordem or 0
        resp.dificuldade = body.dificuldade or dif_padrao
    return resp


@router.get("", response_model=list[FuncaoResponse])
async def listar_funcoes(
    atividade_uuid: str | None = Query(default=None),
    atividadeUuid: str | None = Query(default=None),
    busca: str | None = Query(default=None, description="Filtro por nome ou descrição"),
    dificuldade: str | None = Query(default=None, description="Filtro por dificuldade padrão"),
    session: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Lista funções da biblioteca com filtros opcionais (busca, dificuldade).
    Se atividade_uuid for informado, retorna as funções associadas à atividade.
    """
    target_atv = atividade_uuid or atividadeUuid
    if target_atv:
        query = (
            select(Funcao, AtividadeFuncao)
            .join(AtividadeFuncao, AtividadeFuncao.funcao_uuid == Funcao.uuid)
            .where(AtividadeFuncao.atividade_uuid == target_atv)
            .order_by(AtividadeFuncao.ordem.asc(), Funcao.created_at.asc())
        )
        result = await session.execute(query)
        rows = result.all()
        responses = []
        for f, af in rows:
            r = FuncaoResponse.model_validate(f)
            r.atividade_uuid = af.atividade_uuid
            r.pontos = float(af.peso)
            r.ordem = af.ordem
            r.dificuldade = af.dificuldade
            responses.append(r)
        return responses

    # Alunos não têm acesso à biblioteca global de funções
    if current_user and current_user.tipo == 'aluno':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso não autorizado: alunos não podem visualizar a biblioteca de funções."
        )

    # Consulta padrão na biblioteca de funções (professores / administradores)
    query = select(Funcao).options(selectinload(Funcao.casos_teste))
    if busca:
        termo = f"%{busca.strip()}%"
        query = query.where(
            or_(
                Funcao.nome_funcao.ilike(termo),
                Funcao.descricao.ilike(termo),
            )
        )
    if dificuldade:
        query = query.where(Funcao.dificuldade_padrao == dificuldade)

    query = query.order_by(Funcao.created_at.asc())
    result = await session.execute(query)
    funcoes = result.scalars().all()
    responses = []
    for f in funcoes:
        r = FuncaoResponse.model_validate(f)
        r.total_casos_teste = len(f.casos_teste) if f.casos_teste else 0
        responses.append(r)
    return responses


@router.get("/{funcao_uuid}", response_model=FuncaoDetailResponse)
async def detalhe_funcao(
    funcao_uuid: str,
    session: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Retorna detalhes de uma função da biblioteca com seus casos de teste canônicos (restrito a professores)."""
    if current_user.tipo != "professor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso não autorizado: alunos não podem visualizar a biblioteca de funções."
        )

    result = await session.execute(
        select(Funcao)
        .options(selectinload(Funcao.casos_teste))
        .where(Funcao.uuid == funcao_uuid)
    )
    funcao = result.scalar_one_or_none()

    if not funcao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Função não encontrada na biblioteca"
        )

    # Ordenar casos de teste canônicos por número
    funcao.casos_teste = sorted(funcao.casos_teste, key=lambda c: c.numero)
    resp = FuncaoDetailResponse.model_validate(funcao)
    resp.total_casos_teste = len(funcao.casos_teste)
    return resp



@router.put("/{funcao_uuid}", response_model=FuncaoResponse)
async def atualizar_funcao(
    funcao_uuid: str,
    body: FuncaoUpdate,
    session: AsyncSession = Depends(get_db),
):
    """
    Atualiza uma função na biblioteca global.
    Alterações na biblioteca não alteram configurações contextuais prévias de atividades.
    """
    result = await session.execute(
        select(Funcao).where(Funcao.uuid == funcao_uuid)
    )
    funcao = result.scalar_one_or_none()
    if not funcao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Função não encontrada na biblioteca"
        )

    if body.nome_funcao is not None:
        funcao.nome_funcao = body.nome_funcao
    if body.parametros is not None:
        funcao.parametros = [p.model_dump() for p in body.parametros]
    if body.retorno is not None:
        funcao.retorno = body.retorno.model_dump()
    if body.descricao is not None:
        funcao.descricao = body.descricao
    if body.dificuldade_padrao is not None:
        funcao.dificuldade_padrao = body.dificuldade_padrao
    elif body.dificuldade is not None:
        funcao.dificuldade_padrao = body.dificuldade
    if body.max_tentativas is not None:
        funcao.max_tentativas = body.max_tentativas
    if body.dicas is not None:
        funcao.dicas = body.dicas

    await session.flush()
    await session.refresh(funcao)
    logger.info("Funcao atualizada na biblioteca: %s (uuid=%s)", funcao.nome_funcao, funcao.uuid)
    return FuncaoResponse.model_validate(funcao)


@router.delete("/{funcao_uuid}", status_code=204)
async def remover_funcao(
    funcao_uuid: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Remove uma função da biblioteca.
    Se a função estiver vinculada a qualquer atividade, a exclusão é bloqueada com HTTP 409.
    """
    result = await session.execute(
        select(Funcao).where(Funcao.uuid == funcao_uuid)
    )
    funcao = result.scalar_one_or_none()
    if not funcao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Função não encontrada na biblioteca"
        )

    # Validar integridade referencial com AtividadeFuncao
    result_af = await session.execute(
        select(func.count(AtividadeFuncao.uuid))
        .where(AtividadeFuncao.funcao_uuid == funcao_uuid)
    )
    qtd_atividades = result_af.scalar() or 0
    if qtd_atividades > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Não é possível excluir a função pois ela está associada a {qtd_atividades} atividade(s)."
        )

    await session.delete(funcao)
    await session.flush()
    logger.info("Funcao removida da biblioteca: %s (uuid=%s)", funcao.nome_funcao, funcao_uuid)
    return None


# ---- CASOS DE TESTE CANÔNICOS ----

@router.post("/{funcao_uuid}/casos-teste", status_code=201)
async def criar_casos_teste(
    funcao_uuid: str,
    body: CasoTesteCreate | list[CasoTesteCreate],
    session: AsyncSession = Depends(get_db),
):
    """
    Cadastra caso(s) de teste canônico(s) vinculados a uma função na biblioteca.
    Aceita um objeto ou uma lista.
    """
    # Verificar função
    result = await session.execute(
        select(Funcao).where(Funcao.uuid == funcao_uuid)
    )
    funcao = result.scalar_one_or_none()
    if not funcao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Função não encontrada na biblioteca"
        )

    items = body if isinstance(body, list) else [body]

    # Obter próximo número sequencial
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

    logger.info("%d caso(s) criados para a funcao %s na biblioteca", len(criados), funcao.nome_funcao)

    result_list = [CasoTesteResponse.model_validate(c) for c in criados]
    return result_list if len(result_list) > 1 else result_list[0]


@router.get("/{funcao_uuid}/casos-teste", response_model=list[CasoTesteResponse])
async def listar_casos_teste(
    funcao_uuid: str,
    session: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Lista todos os casos de teste canônicos de uma função na biblioteca (restrito a professores)."""
    if current_user.tipo != "professor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso não autorizado: alunos não podem visualizar a biblioteca de funções."
        )

    result = await session.execute(
        select(Funcao).where(Funcao.uuid == funcao_uuid)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Função não encontrada na biblioteca"
        )

    result = await session.execute(
        select(CasoTeste)
        .where(CasoTeste.funcao_uuid == funcao_uuid)
        .order_by(CasoTeste.numero.asc())
    )
    casos = result.scalars().all()
    return [CasoTesteResponse.model_validate(c) for c in casos]


@router.put("/{funcao_uuid}/casos-teste/{caso_uuid}", response_model=CasoTesteResponse)
async def atualizar_caso_teste(
    funcao_uuid: str,
    caso_uuid: str,
    body: CasoTesteUpdate,
    session: AsyncSession = Depends(get_db),
):
    """Atualiza um caso de teste canônico de uma função na biblioteca."""
    result = await session.execute(
        select(CasoTeste).where(
            CasoTeste.uuid == caso_uuid,
            CasoTeste.funcao_uuid == funcao_uuid,
        )
    )
    caso = result.scalar_one_or_none()
    if not caso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Caso de teste não encontrado para esta função",
        )

    if body.inputs is not None:
        caso.inputs = body.inputs
    if body.output_esperado is not None:
        caso.output_esperado = body.output_esperado
    if body.descricao is not None:
        caso.descricao = body.descricao
    if body.numero is not None:
        caso.numero = body.numero

    await session.flush()
    await session.refresh(caso)
    return CasoTesteResponse.model_validate(caso)


@router.delete("/{funcao_uuid}/casos-teste/{caso_uuid}", status_code=204)
async def remover_caso_teste(
    funcao_uuid: str,
    caso_uuid: str,
    session: AsyncSession = Depends(get_db),
):
    """Remove um caso de teste canônico de uma função na biblioteca."""
    result = await session.execute(
        select(CasoTeste).where(
            CasoTeste.uuid == caso_uuid,
            CasoTeste.funcao_uuid == funcao_uuid,
        )
    )
    caso = result.scalar_one_or_none()
    if not caso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Caso de teste não encontrado para esta função",
        )

    await session.delete(caso)
    await session.flush()
    return None

