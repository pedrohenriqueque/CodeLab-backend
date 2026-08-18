"""
Endpoint de submissões — fluxo end-to-end de avaliação.

Rotas:
    POST /api/submissoes              → Submeter código para avaliação
    GET  /api/submissoes              → Listar submissões
    GET  /api/submissoes/{uuid}       → Detalhe de submissão
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_db, get_current_user
from app.db.models import Funcao, CasoTeste, Submissao, Usuario
from app.schemas.submissao import SubmissaoCreate, SubmissaoResponse, SubmissaoListResponse, SubmissaoFeedbackUpdate, CasoResultado
from app.services.avaliador_service import avaliador_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/submissoes", tags=["Submissões"])


@router.post("", response_model=SubmissaoResponse)
async def criar_submissao(
    body: SubmissaoCreate,
    session: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Submete código C para avaliação automática.

    Fluxo:
    1. Busca função e casos de teste no banco
    2. Cria registro Submissao com status="compilando"
    3. Gera programa C de teste, envia para Judge0 (async)
    4. Parseia resultado, calcula nota proporcional
    5. Atualiza Submissao com resultado e status="avaliado"
    6. Retorna JSON com nota e detalhes dos casos
    """
    # 1. Buscar função
    result = await session.execute(
        select(Funcao)
        .options(selectinload(Funcao.casos_teste), selectinload(Funcao.atividade))
        .where(Funcao.uuid == body.funcao_uuid)
    )
    funcao = result.scalar_one_or_none()
    if not funcao:
        raise HTTPException(status_code=404, detail="Função não encontrada")

    # Validar que existem casos de teste
    casos_teste = sorted(funcao.casos_teste, key=lambda c: c.numero)
    if not casos_teste:
        raise HTTPException(
            status_code=400,
            detail="Nenhum caso de teste cadastrado para esta função",
        )

    # Validar regras da atividade (NEVER TRUST FRONT END)
    if current_user.tipo == 'aluno':
        if funcao.atividade.status != 'publicado':
            raise HTTPException(
                status_code=403,
                detail="Esta atividade não está aberta para submissões."
            )
        
        from datetime import datetime, timezone
        if funcao.atividade.data_fechamento:
            agora = datetime.now(timezone.utc)
            fechamento = funcao.atividade.data_fechamento
            if fechamento.tzinfo is None:
                fechamento = fechamento.replace(tzinfo=timezone.utc)
            if agora > fechamento:
                raise HTTPException(
                    status_code=403,
                    detail="O prazo para submissão nesta atividade já encerrou."
                )

    # 2. Contar tentativas anteriores
    result = await session.execute(
        select(Submissao)
        .where(Submissao.funcao_uuid == body.funcao_uuid)
        .where(Submissao.aluno_uuid == current_user.uuid)
        .order_by(Submissao.tentativa_numero.desc())
    )
    ultima = result.scalars().first()
    
    if funcao.atividade.tipo == 'prova' and ultima is not None:
        raise HTTPException(
            status_code=400,
            detail="Esta é uma prova. Você já utilizou sua única tentativa de submissão."
        )

    tentativa = (ultima.tentativa_numero + 1) if ultima else 1

    # 3. Criar submissão com status "compilando"
    submissao = Submissao(
        funcao_uuid=body.funcao_uuid,
        aluno_uuid=current_user.uuid,
        codigo_submetido=body.codigo,
        status="compilando",
        tentativa_numero=tentativa,
    )
    session.add(submissao)
    await session.flush()

    logger.info(
        "Submissao %s criada para funcao %s (tentativa %d, %d casos)",
        submissao.uuid[:8], funcao.nome_funcao, tentativa, len(casos_teste),
    )

    try:
        # 4. Preparar dicts para o avaliador
        funcao_dict = {
            "nome_funcao": funcao.nome_funcao,
            "parametros": funcao.parametros,
            "retorno": funcao.retorno,
            "pontos": float(funcao.pontos),
        }
        casos_dict = [
            {
                "inputs": c.inputs,
                "output_esperado": c.output_esperado,
                "descricao": c.descricao,
            }
            for c in casos_teste
        ]

        # 5. Avaliar (async — não bloqueia o event loop)
        submissao.status = "executando"
        await session.flush()

        resultado = await avaliador_service.avaliar(funcao_dict, casos_dict, body.codigo)

        # 6. Salvar resultado
        submissao.nota = resultado["nota"]
        submissao.status = "avaliado"
        submissao.resultado_json = resultado
        await session.flush()

        logger.info(
            "Submissao %s finalizada: nota=%.2f/%s",
            submissao.uuid[:8], resultado["nota"], funcao.pontos,
        )

        response = SubmissaoResponse(
            submissao_uuid=submissao.uuid,
            funcao=funcao.nome_funcao,
            nota=resultado.get("nota", 0.0),
            pontos_maximo=float(funcao.pontos),
            total_casos=resultado.get("total_casos", len(casos_teste)),
            casos_passados=resultado.get("casos_passados", 0),
            casos=[
                CasoResultado(
                    numero=c["numero"],
                    status=c["status"],
                    expected=c.get("expected"),
                    got=c.get("got")
                )
                for c in resultado.get("casos", [])
            ],
            erro_compilacao=resultado.get("erro_compilacao"),
            erro_execucao=resultado.get("erro_execucao"),
        )

        if funcao.atividade.tipo == 'prova' and not funcao.atividade.notas_liberadas and current_user.tipo == 'aluno':
            response.nota = 0.0
            response.pontos_maximo = 0.0
            response.total_casos = 0
            response.casos_passados = 0
            response.casos = []
            response.erro_compilacao = None
            response.erro_execucao = None
            
        return response

    except Exception as e:
        submissao.status = "erro"
        submissao.resultado_json = {"erro": str(e)}
        submissao.nota = 0.0
        await session.flush()

        logger.error("Erro na submissao %s: %s", submissao.uuid[:8], e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[SubmissaoListResponse])
async def listar_submissoes(
    funcao_uuid: str | None = Query(default=None, alias="funcaoUuid"),
    status: str | None = None,
    session: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Lista submissões com filtros opcionais."""
    atividade_tipo: str | None = None
    if funcao_uuid:
        funcao_result = await session.execute(
            select(Funcao)
            .options(selectinload(Funcao.atividade))
            .where(Funcao.uuid == funcao_uuid)
        )
        funcao_ref = funcao_result.scalar_one_or_none()
        if funcao_ref:
            atividade_tipo = funcao_ref.atividade.tipo

    query = select(Submissao).options(selectinload(Submissao.aluno), selectinload(Submissao.funcao).selectinload(Funcao.atividade))

    if current_user.tipo == 'aluno':
        query = query.where(Submissao.aluno_uuid == current_user.uuid)

    if funcao_uuid:
        query = query.where(Submissao.funcao_uuid == funcao_uuid)
    if status:
        query = query.where(Submissao.status == status)

    if atividade_tipo == "prova":
        # Provas: ordenar estritamente por data/horario de submissao.
        query = query.order_by(Submissao.data_submissao.desc())
    else:
        # Exercicios: agrupar por aluno e ordenar cronologicamente por submissao.
        query = query.order_by(Submissao.aluno_uuid.asc(), Submissao.data_submissao.asc())

    result = await session.execute(query)
    submissoes = result.scalars().all()

    tentativas_por_aluno: dict[str, int] = {}
    responses = []
    for s in submissoes:
        tentativa_numero = s.tentativa_numero
        if atividade_tipo != "prova" and s.aluno_uuid:
            tentativas_por_aluno[s.aluno_uuid] = tentativas_por_aluno.get(s.aluno_uuid, 0) + 1
            tentativa_numero = tentativas_por_aluno[s.aluno_uuid]

        s_resp = SubmissaoListResponse(
            uuid=s.uuid,
            funcao_uuid=s.funcao_uuid,
            aluno_nome=s.aluno.nome if s.aluno else None,
            codigo_submetido=s.codigo_submetido,
            data_submissao=s.data_submissao,
            tentativa_numero=tentativa_numero,
            status=s.status,
            nota=float(s.nota) if s.nota is not None else None,
            resultado_json=s.resultado_json,
            feedback_professor=s.feedback_professor,
        )
        if s.funcao.atividade.tipo == 'prova' and not s.funcao.atividade.notas_liberadas and current_user.tipo == 'aluno':
            s_resp.nota = None
            s_resp.resultado_json = None
            
        responses.append(s_resp)
        
    return responses


@router.get("/{submissao_uuid}", response_model=SubmissaoListResponse)
async def detalhe_submissao(
    submissao_uuid: str,
    session: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Retorna detalhes completos de uma submissão."""
    query = select(Submissao).options(selectinload(Submissao.aluno), selectinload(Submissao.funcao).selectinload(Funcao.atividade))
    if current_user.tipo == 'aluno':
        query = query.where(Submissao.aluno_uuid == current_user.uuid)
        
    result = await session.execute(
        query
        .where(Submissao.uuid == submissao_uuid)
    )
    submissao = result.scalar_one_or_none()
    if not submissao:
        raise HTTPException(status_code=404, detail="Submissão não encontrada")

    s_resp = SubmissaoListResponse(
        uuid=submissao.uuid,
        funcao_uuid=submissao.funcao_uuid,
        aluno_nome=submissao.aluno.nome if submissao.aluno else None,
        codigo_submetido=submissao.codigo_submetido,
        data_submissao=submissao.data_submissao,
        tentativa_numero=submissao.tentativa_numero,
        status=submissao.status,
        nota=float(submissao.nota) if submissao.nota is not None else None,
        resultado_json=submissao.resultado_json,
        feedback_professor=submissao.feedback_professor,
    )
    
    if submissao.funcao.atividade.tipo == 'prova' and not submissao.funcao.atividade.notas_liberadas and current_user.tipo == 'aluno':
        s_resp.nota = None
        s_resp.resultado_json = None

    return s_resp

@router.patch("/{submissao_uuid}/feedback", response_model=SubmissaoListResponse)
async def atualizar_feedback(
    submissao_uuid: str,
    body: SubmissaoFeedbackUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Atualiza o feedback manual do professor para uma submissão."""
    if current_user.tipo == 'aluno':
        raise HTTPException(status_code=403, detail="Alunos não podem adicionar ou editar feedbacks")
        
    result = await session.execute(
        select(Submissao)
        .options(selectinload(Submissao.aluno))
        .where(Submissao.uuid == submissao_uuid)
    )
    submissao = result.scalar_one_or_none()
    if not submissao:
        raise HTTPException(status_code=404, detail="Submissão não encontrada")

    submissao.feedback_professor = body.feedback_professor
    await session.commit()
    await session.refresh(submissao)

    return SubmissaoListResponse(
        uuid=submissao.uuid,
        funcao_uuid=submissao.funcao_uuid,
        aluno_nome=submissao.aluno.nome if submissao.aluno else None,
        codigo_submetido=submissao.codigo_submetido,
        data_submissao=submissao.data_submissao,
        tentativa_numero=submissao.tentativa_numero,
        status=submissao.status,
        nota=float(submissao.nota) if submissao.nota is not None else None,
        resultado_json=submissao.resultado_json,
        feedback_professor=submissao.feedback_professor,
    )
