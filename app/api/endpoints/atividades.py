"""
Endpoints CRUD para Atividades e Associação de Funções (N:N).

Rotas:
    POST   /api/atividades                                         → Criar atividade
    GET    /api/atividades                                         → Listar atividades
    GET    /api/atividades/{uuid}                                  → Detalhe de atividade (com funções e casos)
    PATCH  /api/atividades/{uuid}                                  → Atualizar atividade (campos + status)

    POST   /api/atividades/{uuid}/funcoes                          → Associar função à atividade
    PATCH  /api/atividades/{uuid}/funcoes/{funcao_uuid}            → Atualizar associação (dificuldade, peso, ordem, casos)
    DELETE /api/atividades/{uuid}/funcoes/{funcao_uuid}            → Desassociar função da atividade
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, desc
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_db, get_current_user, get_optional_current_user
from app.db.models import (
    Atividade,
    AtividadeFuncao,
    AtividadeFuncaoCasoTeste,
    Funcao,
    CasoTeste,
    EntregaAtividade,
    Submissao,
    Usuario,
)
from app.schemas.atividade import (
    AtividadeCreate,
    AtividadeUpdate,
    AtividadeResponse,
    AtividadeFuncaoAssociarRequest,
    AtividadeFuncaoUpdateRequest,
    AtividadeFuncaoResponse,
    AtividadeFuncaoCasoTesteResponse,
    EntregaAtividadeResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/atividades", tags=["Atividades"])


def _montar_atividade_response(
    atividade: Atividade,
    status_entrega: str | None = None,
    current_user: Usuario | None = None,
) -> AtividadeResponse:
    """Helper para serializar a atividade com as funções associadas e seus casos de teste contextuais."""
    funcoes_resp: list[AtividadeFuncaoResponse] = []
    
    for af in atividade.atividades_funcoes:
        func = af.funcao
        casos_resp: list[AtividadeFuncaoCasoTesteResponse] = []
        
        # Mapear casos de teste da configuração contextual
        for cfg in af.casos_teste_config:
            ct = cfg.caso_teste
            if ct:
                is_oculto_para_aluno = cfg.oculto and (current_user is not None and current_user.tipo == 'aluno')
                casos_resp.append(
                    AtividadeFuncaoCasoTesteResponse(
                        uuid=cfg.uuid,
                        caso_teste_uuid=ct.uuid,
                        numero=ct.numero,
                        oculto=cfg.oculto,
                        inputs=None if is_oculto_para_aluno else ct.inputs,
                        output_esperado=None if is_oculto_para_aluno else ct.output_esperado,
                        descricao=ct.descricao,
                    )
                )
        # Ordenar casos contextuais por número
        casos_resp.sort(key=lambda c: c.numero)

        funcoes_resp.append(
            AtividadeFuncaoResponse(
                uuid=af.uuid,
                funcao_uuid=func.uuid,
                nome_funcao=func.nome_funcao,
                descricao=func.descricao,
                parametros=func.parametros,
                retorno=func.retorno,
                dificuldade=af.dificuldade,
                dificuldade_padrao=func.dificuldade_padrao,
                peso=float(af.peso),
                ordem=af.ordem,
                casos_teste=casos_resp,
            )
        )

    # Ordenar funções pela ordem definida na atividade
    funcoes_resp.sort(key=lambda f: f.ordem)

    return AtividadeResponse(
        uuid=atividade.uuid,
        professor_uuid=atividade.professor_uuid,
        titulo=atividade.titulo,
        descricao=atividade.descricao,
        pontuacao_maxima=float(atividade.pontuacao_maxima),
        data_abertura=atividade.data_abertura,
        data_fechamento=atividade.data_fechamento,
        status=atividade.status,
        tipo=atividade.tipo,
        duracao_minutos=atividade.duracao_minutos,
        bloquear_paste=atividade.bloquear_paste,
        notas_liberadas=atividade.notas_liberadas,
        created_at=atividade.created_at,
        status_entrega=status_entrega,
        funcoes=funcoes_resp,
    )


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
    return _montar_atividade_response(atividade)


@router.get("", response_model=list[AtividadeResponse])
async def listar_atividades(
    session: AsyncSession = Depends(get_db),
    current_user: Usuario | None = Depends(get_optional_current_user),
):
    """Lista todas as atividades."""
    result = await session.execute(
        select(Atividade)
        .options(
            selectinload(Atividade.atividades_funcoes)
            .selectinload(AtividadeFuncao.funcao),
            selectinload(Atividade.atividades_funcoes)
            .selectinload(AtividadeFuncao.casos_teste_config)
            .selectinload(AtividadeFuncaoCasoTeste.caso_teste),
        )
        .order_by(Atividade.created_at.desc())
    )
    atividades = result.scalars().all()

    entregas_map: dict[str, str] = {}
    if current_user and current_user.tipo == 'aluno':
        res_entregas = await session.execute(
            select(EntregaAtividade).where(
                EntregaAtividade.aluno_uuid == current_user.uuid,
                EntregaAtividade.status == "entregue"
            )
        )
        for ent in res_entregas.scalars().all():
            entregas_map[ent.atividade_uuid] = "entregue"

    respostas = []
    for a in atividades:
        st_entrega = None
        if current_user and current_user.tipo == 'aluno':
            st_entrega = entregas_map.get(a.uuid, "em_andamento")
        respostas.append(_montar_atividade_response(a, status_entrega=st_entrega, current_user=current_user))

    return respostas


@router.get("/{atividade_uuid}", response_model=AtividadeResponse)
async def detalhe_atividade(
    atividade_uuid: str,
    session: AsyncSession = Depends(get_db),
    current_user: Usuario | None = Depends(get_optional_current_user),
):
    """Retorna detalhes de uma atividade com suas funções e casos contextuais."""
    result = await session.execute(
        select(Atividade)
        .options(
            selectinload(Atividade.atividades_funcoes)
            .selectinload(AtividadeFuncao.funcao),
            selectinload(Atividade.atividades_funcoes)
            .selectinload(AtividadeFuncao.casos_teste_config)
            .selectinload(AtividadeFuncaoCasoTeste.caso_teste),
        )
        .where(Atividade.uuid == atividade_uuid)
    )
    atividade = result.scalar_one_or_none()

    if not atividade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atividade não encontrada"
        )

    st_entrega = None
    if current_user and current_user.tipo == 'aluno':
        res_entrega = await session.execute(
            select(EntregaAtividade).where(
                EntregaAtividade.aluno_uuid == current_user.uuid,
                EntregaAtividade.atividade_uuid == atividade.uuid,
                EntregaAtividade.status == "entregue"
            )
        )
        if res_entrega.scalar_one_or_none():
            st_entrega = "entregue"
        else:
            st_entrega = "em_andamento"

    return _montar_atividade_response(atividade, status_entrega=st_entrega, current_user=current_user)


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
        .options(
            selectinload(Atividade.atividades_funcoes)
            .selectinload(AtividadeFuncao.funcao),
            selectinload(Atividade.atividades_funcoes)
            .selectinload(AtividadeFuncao.casos_teste_config)
            .selectinload(AtividadeFuncaoCasoTeste.caso_teste),
        )
        .where(Atividade.uuid == atividade_uuid)
    )
    atividade = result.scalar_one_or_none()

    if not atividade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atividade não encontrada"
        )

    update_data = body.model_dump(exclude_unset=True)

    # ── Validar transição de status ──────────────────────────────
    novo_status = update_data.get("status")
    if novo_status and novo_status != atividade.status:
        par = (atividade.status, novo_status)
        if par not in TRANSICOES_VALIDAS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transição de status inválida: {atividade.status} → {novo_status}",
            )

        # Para publicar, exigir pelo menos 1 função
        if novo_status == "publicado" and not atividade.atividades_funcoes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não é possível publicar: a atividade precisa ter pelo menos 1 função associada.",
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
    return _montar_atividade_response(atividade)


# =====================================================================
# ASSOCIAÇÃO N:N ATIVIDADE × FUNÇÃO
# =====================================================================

@router.post("/{atividade_uuid}/funcoes", response_model=AtividadeFuncaoResponse, status_code=201)
async def associar_funcao_atividade(
    atividade_uuid: str,
    body: AtividadeFuncaoAssociarRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Associa uma função existente da biblioteca à atividade com parametrizações contextuais.
    Não cria nova função nem duplica dados canônicos da biblioteca.
    """
    # 1. Verificar se a atividade existe
    res_atv = await session.execute(
        select(Atividade).where(Atividade.uuid == atividade_uuid)
    )
    atividade = res_atv.scalar_one_or_none()
    if not atividade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atividade não encontrada"
        )

    # 2. Verificar se a função existe na biblioteca
    res_func = await session.execute(
        select(Funcao)
        .options(selectinload(Funcao.casos_teste))
        .where(Funcao.uuid == body.funcao_uuid)
    )
    funcao = res_func.scalar_one_or_none()
    if not funcao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Função não encontrada na biblioteca"
        )

    # 3. Validar se a função já está associada a esta atividade (rejeitar duplicidade)
    res_existente = await session.execute(
        select(AtividadeFuncao).where(
            AtividadeFuncao.atividade_uuid == atividade_uuid,
            AtividadeFuncao.funcao_uuid == body.funcao_uuid,
        )
    )
    if res_existente.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta função já está associada a esta atividade."
        )

    # 4. Determinar dificuldade contextual (se não informada, usa a dificuldade_padrao da função)
    dificuldade_contextual = body.dificuldade or funcao.dificuldade_padrao or "medio"

    # 5. Criar registro associativo AtividadeFuncao
    af = AtividadeFuncao(
        atividade_uuid=atividade_uuid,
        funcao_uuid=funcao.uuid,
        dificuldade=dificuldade_contextual,
        peso=body.peso,
        ordem=body.ordem,
    )
    session.add(af)
    await session.flush()

    # 6. Configurar casos de teste contextuais
    # Mapear casos canônicos válidos da função
    casos_canonicos = {c.uuid: c for c in funcao.casos_teste}

    casos_config_criados = []
    if body.casos_teste is not None:
        # Validar compatibilidade: todos os casos devem pertencer a esta função
        for item in body.casos_teste:
            if item.caso_teste_uuid not in casos_canonicos:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"O caso de teste {item.caso_teste_uuid} não pertence à função {funcao.nome_funcao}."
                )
            cfg = AtividadeFuncaoCasoTeste(
                atividade_funcao_uuid=af.uuid,
                caso_teste_uuid=item.caso_teste_uuid,
                oculto=item.oculto,
            )
            session.add(cfg)
            casos_config_criados.append((cfg, casos_canonicos[item.caso_teste_uuid]))
    else:
        # Padrão: se não informou casos_teste, incluir todos os casos canônicos como visíveis
        for ct in sorted(funcao.casos_teste, key=lambda c: c.numero):
            cfg = AtividadeFuncaoCasoTeste(
                atividade_funcao_uuid=af.uuid,
                caso_teste_uuid=ct.uuid,
                oculto=False,
            )
            session.add(cfg)
            casos_config_criados.append((cfg, ct))

    await session.flush()
    await session.refresh(af)

    # Montar resposta contextual
    casos_resp = [
        AtividadeFuncaoCasoTesteResponse(
            uuid=cfg.uuid,
            caso_teste_uuid=ct.uuid,
            numero=ct.numero,
            oculto=cfg.oculto,
            inputs=ct.inputs,
            output_esperado=ct.output_esperado,
            descricao=ct.descricao,
        )
        for cfg, ct in casos_config_criados
    ]
    casos_resp.sort(key=lambda c: c.numero)

    logger.info(
        "Funcao %s associada a atividade %s (dificuldade=%s, peso=%.2f, casos=%d)",
        funcao.nome_funcao, atividade.titulo, dificuldade_contextual, float(body.peso), len(casos_resp),
    )

    return AtividadeFuncaoResponse(
        uuid=af.uuid,
        funcao_uuid=funcao.uuid,
        nome_funcao=funcao.nome_funcao,
        descricao=funcao.descricao,
        parametros=funcao.parametros,
        retorno=funcao.retorno,
        dificuldade=af.dificuldade,
        dificuldade_padrao=funcao.dificuldade_padrao,
        peso=float(af.peso),
        ordem=af.ordem,
        casos_teste=casos_resp,
    )


@router.patch("/{atividade_uuid}/funcoes/{funcao_uuid}", response_model=AtividadeFuncaoResponse)
async def atualizar_funcao_atividade(
    atividade_uuid: str,
    funcao_uuid: str,
    body: AtividadeFuncaoUpdateRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Atualiza as configurações contextuais de uma função dentro de uma atividade
    (dificuldade, peso, ordem e/ou casos de teste selecionados com visibilidade).
    """
    # 1. Buscar a associação existente
    res_af = await session.execute(
        select(AtividadeFuncao)
        .options(
            selectinload(AtividadeFuncao.funcao).selectinload(Funcao.casos_teste),
            selectinload(AtividadeFuncao.casos_teste_config).selectinload(AtividadeFuncaoCasoTeste.caso_teste),
        )
        .where(
            AtividadeFuncao.atividade_uuid == atividade_uuid,
            AtividadeFuncao.funcao_uuid == funcao_uuid,
        )
    )
    af = res_af.scalar_one_or_none()
    if not af:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Função não está associada a esta atividade"
        )

    # 2. Atualizar campos contextuais simples
    if body.dificuldade is not None:
        af.dificuldade = body.dificuldade
    if body.peso is not None:
        af.peso = body.peso
    if body.ordem is not None:
        af.ordem = body.ordem

    # 3. Atualizar casos de teste se informados
    if body.casos_teste is not None:
        casos_canonicos = {c.uuid: c for c in af.funcao.casos_teste}
        
        # Validar compatibilidade
        for item in body.casos_teste:
            if item.caso_teste_uuid not in casos_canonicos:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"O caso de teste {item.caso_teste_uuid} não pertence à função {af.funcao.nome_funcao}."
                )

        # Limpar configurações antigas pela coleção do relacionamento
        af.casos_teste_config.clear()
        await session.flush()

        # Inserir novas configurações
        for item in body.casos_teste:
            af.casos_teste_config.append(
                AtividadeFuncaoCasoTeste(
                    atividade_funcao_uuid=af.uuid,
                    caso_teste_uuid=item.caso_teste_uuid,
                    oculto=item.oculto,
                )
            )

    await session.flush()
    
    # Recarregar associação atualizada
    res_af_updated = await session.execute(
        select(AtividadeFuncao)
        .options(
            selectinload(AtividadeFuncao.funcao),
            selectinload(AtividadeFuncao.casos_teste_config).selectinload(AtividadeFuncaoCasoTeste.caso_teste),
        )
        .where(AtividadeFuncao.uuid == af.uuid)
    )
    af_updated = res_af_updated.scalar_one()

    casos_resp = [
        AtividadeFuncaoCasoTesteResponse(
            uuid=cfg.uuid,
            caso_teste_uuid=cfg.caso_teste.uuid,
            numero=cfg.caso_teste.numero,
            oculto=cfg.oculto,
            inputs=cfg.caso_teste.inputs,
            output_esperado=cfg.caso_teste.output_esperado,
            descricao=cfg.caso_teste.descricao,
        )
        for cfg in af_updated.casos_teste_config if cfg.caso_teste
    ]
    casos_resp.sort(key=lambda c: c.numero)

    return AtividadeFuncaoResponse(
        uuid=af_updated.uuid,
        funcao_uuid=af_updated.funcao.uuid,
        nome_funcao=af_updated.funcao.nome_funcao,
        descricao=af_updated.funcao.descricao,
        parametros=af_updated.funcao.parametros,
        retorno=af_updated.funcao.retorno,
        dificuldade=af_updated.dificuldade,
        dificuldade_padrao=af_updated.funcao.dificuldade_padrao,
        peso=float(af_updated.peso),
        ordem=af_updated.ordem,
        casos_teste=casos_resp,
    )


@router.delete("/{atividade_uuid}/funcoes/{funcao_uuid}", status_code=204)
async def remover_funcao_atividade(
    atividade_uuid: str,
    funcao_uuid: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Remove uma função de uma atividade.
    Exclui apenas a associação AtividadeFuncao e suas configurações contextuais,
    preservando a Função e seus Casos de Teste na biblioteca global.
    """
    res_af = await session.execute(
        select(AtividadeFuncao).where(
            AtividadeFuncao.atividade_uuid == atividade_uuid,
            AtividadeFuncao.funcao_uuid == funcao_uuid,
        )
    )
    af = res_af.scalar_one_or_none()
    if not af:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associação entre atividade e função não encontrada"
        )

    await session.delete(af)
    await session.flush()
    logger.info("Associacao removida: atividade=%s funcao=%s", atividade_uuid, funcao_uuid)
    return None


@router.post("/{atividade_uuid}/entregar", response_model=EntregaAtividadeResponse)
async def entregar_atividade(
    atividade_uuid: str,
    session: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Realiza a entrega final consolidada da atividade pelo aluno (RN14).
    
    Regras:
    1. Apenas alunos autenticados podem entregar.
    2. Atividade deve existir e estar 'publicada'.
    3. Respeitar data de fechamento da atividade se configurada.
    4. Idempotência / unicidade: Se o aluno já entregou a atividade, rejeitar com HTTP 400.
    5. Consolidação da nota: Para cada função associada à atividade, recupera a melhor nota
       dentre as submissões avaliadas daquele aluno para aquela função nessa atividade.
    6. Cria e salva EntregaAtividade com status='entregue' e data_entrega=agora.
    7. Submissões posteriores desta atividade para este aluno passam a ser rejeitadas.
    """
    if current_user.tipo != "aluno":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas alunos podem realizar a entrega de atividades."
        )

    # 1. Verificar se a atividade existe
    res_atv = await session.execute(
        select(Atividade)
        .options(
            selectinload(Atividade.atividades_funcoes)
            .selectinload(AtividadeFuncao.funcao)
        )
        .where(Atividade.uuid == atividade_uuid)
    )
    atividade = res_atv.scalar_one_or_none()
    if not atividade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atividade não encontrada"
        )

    # 2. Verificar status da atividade
    if atividade.status != "publicado":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta atividade não está aberta para entrega."
        )

    # 3. Verificar prazo de fechamento
    if atividade.data_fechamento:
        agora = datetime.now(timezone.utc)
        fechamento = atividade.data_fechamento
        if fechamento.tzinfo is None:
            fechamento = fechamento.replace(tzinfo=timezone.utc)
        if agora > fechamento:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="O prazo para entrega desta atividade já encerrou."
            )

    # 4. Verificar se o aluno já realizou a entrega final
    res_entrega_existente = await session.execute(
        select(EntregaAtividade).where(
            EntregaAtividade.atividade_uuid == atividade.uuid,
            EntregaAtividade.aluno_uuid == current_user.uuid,
            EntregaAtividade.status == "entregue"
        )
    )
    if res_entrega_existente.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Atividade já entregue pelo aluno. Não é permitida nova entrega."
        )

    # 5. Consolidar nota final a partir das melhores submissões de cada função associada
    total_nota = 0.0
    for af in atividade.atividades_funcoes:
        res_sub = await session.execute(
            select(Submissao)
            .where(
                Submissao.atividade_uuid == atividade.uuid,
                Submissao.funcao_uuid == af.funcao_uuid,
                Submissao.aluno_uuid == current_user.uuid,
                Submissao.status == "avaliado",
            )
            .order_by(desc(Submissao.nota))
        )
        melhor_sub = res_sub.scalars().first()
        if melhor_sub and melhor_sub.nota is not None:
            total_nota += float(melhor_sub.nota)

    # Arredondar para 2 casas decimais
    total_nota = round(total_nota, 2)
    pontos_max = float(atividade.pontuacao_maxima)
    if total_nota > pontos_max:
        total_nota = pontos_max

    # 6. Criar registro de EntregaAtividade
    agora_entrega = datetime.now(timezone.utc)
    entrega = EntregaAtividade(
        aluno_uuid=current_user.uuid,
        atividade_uuid=atividade.uuid,
        status="entregue",
        nota_final=total_nota,
        data_entrega=agora_entrega,
    )
    session.add(entrega)
    await session.flush()
    await session.refresh(entrega)

    logger.info(
        "Atividade entregue: atv=%s aluno=%s nota_final=%.2f",
        atividade.uuid[:8], current_user.uuid[:8], total_nota
    )

    return EntregaAtividadeResponse(
        uuid=entrega.uuid,
        aluno_uuid=entrega.aluno_uuid,
        atividade_uuid=entrega.atividade_uuid,
        status=entrega.status,
        nota_final=float(entrega.nota_final) if entrega.nota_final is not None else 0.0,
        data_entrega=entrega.data_entrega,
        mensagem="Atividade entregue com sucesso."
    )

