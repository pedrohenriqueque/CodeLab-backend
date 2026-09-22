from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.exceptions import CodelabException, NotFoundError
from ..models.atividade import Atividade
from ..models.funcao_atividade import CasoTesteAtividade, FuncaoAtividade
from ..models.usuario import PerfilUsuario, Usuario
from ..repositories.activity_repository import ActivityRepository
from ..repositories.activity_function_repository import ActivityFunctionRepository
from ..repositories.class_repository import ClassRepository
from ..repositories.enrollment_repository import EnrollmentRepository
from ..repositories.test_case_repository import TestCaseRepository
from ..schemas.atividade import AtualizarAtividadeRequest, CriarAtividadeRequest
from ..schemas.funcao_atividade import AssociarFuncaoAtividadeRequest, ReordenarFuncoesAtividadeRequest
from .function_service import obter_funcao

async def _owned_class(class_id: UUID, professor: Usuario, db: AsyncSession):
    if professor.perfil != PerfilUsuario.PROFESSOR: raise CodelabException("Operação não permitida para este perfil.", 403)
    turma = await ClassRepository(db).get_by_uuid(class_id)
    if turma is None: raise NotFoundError("Turma")
    if turma.professor_uuid != professor.uuid: raise CodelabException("Você não gerencia esta turma.", 403)
    return turma


async def _viewable_activity(activity_id: UUID, usuario: Usuario, db: AsyncSession) -> Atividade:
    atividade = await ActivityRepository(db).get_by_uuid(activity_id)
    if atividade is None:
        raise NotFoundError("Atividade")
    if usuario.perfil == PerfilUsuario.PROFESSOR:
        await _owned_class(atividade.turma_uuid, usuario, db)
        return atividade
    if usuario.perfil == PerfilUsuario.ALUNO:
        matriculado = await EnrollmentRepository(db).exists(atividade.turma_uuid, usuario.uuid)
        if not matriculado or atividade.status == "RASCUNHO":
            raise CodelabException("Atividade não disponível para este aluno.", 403)
        return atividade
    raise CodelabException("Operação não permitida para este perfil.", 403)

async def criar_atividade(dados: CriarAtividadeRequest, professor: Usuario, db: AsyncSession) -> Atividade:
    await _owned_class(dados.turma_uuid, professor, db)
    atividade = Atividade(turma_uuid=dados.turma_uuid, titulo=dados.titulo.strip(), descricao=dados.descricao.strip(), inicio_em=dados.inicio_em, fim_em=dados.fim_em, status="RASCUNHO", tipo=dados.tipo, permitir_multiplas_submissoes=dados.permitir_multiplas_submissoes if dados.tipo == "EXERCICIO" else False, max_tentativas_por_funcao=dados.max_tentativas_por_funcao if dados.tipo == "EXERCICIO" and dados.permitir_multiplas_submissoes else None, mostrar_ocultos_apos_fechamento=dados.mostrar_ocultos_apos_fechamento if dados.tipo == "EXERCICIO" else False)
    await ActivityRepository(db).add(atividade); await db.commit(); await db.refresh(atividade)
    return atividade

async def listar_atividades(usuario: Usuario, db: AsyncSession) -> list[Atividade]:
    turmas = (
        await ClassRepository(db).list_by_professor(usuario.uuid)
        if usuario.perfil == PerfilUsuario.PROFESSOR
        else await ClassRepository(db).list_by_student(usuario.uuid)
        if usuario.perfil == PerfilUsuario.ALUNO
        else None
    )
    if turmas is None:
        raise CodelabException("Operação não permitida para este perfil.", 403)
    atividades = await ActivityRepository(db).list_by_class_ids([turma.uuid for turma in turmas])
    return atividades if usuario.perfil == PerfilUsuario.PROFESSOR else [item for item in atividades if item.status != "RASCUNHO"]

async def obter_atividade(activity_id: UUID, professor: Usuario, db: AsyncSession) -> Atividade:
    return await _viewable_activity(activity_id, professor, db)

async def atualizar_atividade(activity_id: UUID, dados: AtualizarAtividadeRequest, professor: Usuario, db: AsyncSession) -> Atividade:
    atividade = await obter_atividade(activity_id, professor, db)
    if atividade.status != "RASCUNHO": raise CodelabException("Apenas rascunhos podem ser editados.", 409)
    inicio = dados.inicio_em or atividade.inicio_em; fim = dados.fim_em or atividade.fim_em
    if inicio >= fim: raise CodelabException("A data inicial deve anteceder a final.", 422)
    if dados.titulo is not None: atividade.titulo = dados.titulo.strip()
    if dados.descricao is not None: atividade.descricao = dados.descricao.strip()
    if dados.permitir_multiplas_submissoes is not None:
        atividade.permitir_multiplas_submissoes = dados.permitir_multiplas_submissoes if atividade.tipo == "EXERCICIO" else False
    if dados.max_tentativas_por_funcao is not None:
        atividade.max_tentativas_por_funcao = dados.max_tentativas_por_funcao
    if dados.mostrar_ocultos_apos_fechamento is not None:
        atividade.mostrar_ocultos_apos_fechamento = dados.mostrar_ocultos_apos_fechamento if atividade.tipo == "EXERCICIO" else False
    atividade.inicio_em, atividade.fim_em = inicio, fim
    await db.commit(); await db.refresh(atividade)
    return atividade


def _require_draft(atividade: Atividade) -> None:
    if atividade.status != "RASCUNHO":
        raise CodelabException("A composição só pode ser alterada em rascunho.", 409)


async def associar_funcao(
    activity_id: UUID,
    dados: AssociarFuncaoAtividadeRequest,
    professor: Usuario,
    db: AsyncSession,
) -> tuple[FuncaoAtividade, list[CasoTesteAtividade]]:
    atividade = await obter_atividade(activity_id, professor, db)
    _require_draft(atividade)
    origem = await obter_funcao(dados.funcao_uuid, professor, db)
    casos_origem = await TestCaseRepository(db).list_by_function(origem.uuid)
    repository = ActivityFunctionRepository(db)
    interna = FuncaoAtividade(
        uuid=uuid4(),
        atividade_uuid=atividade.uuid,
        nome=origem.nome,
        enunciado=origem.enunciado,
        tipo_retorno=origem.tipo_retorno,
        parametros=deepcopy(origem.parametros),
        dificuldade=(dados.dificuldade or origem.dificuldade).upper(),
        nota_maxima=dados.nota_maxima,
        ordem=await repository.next_order(atividade.uuid),
    )
    await repository.add_function(interna)
    try:
        await db.flush()
        casos_internos = [
        CasoTesteAtividade(
            uuid=uuid4(),
                funcao_atividade_uuid=interna.uuid,
                entradas=deepcopy(caso.entradas),
                retorno_esperado=deepcopy(caso.retorno_esperado),
                visibilidade=caso.visibilidade,
                descricao=caso.descricao,
            )
            for caso in casos_origem
        ]
        for caso in casos_internos:
            await repository.add_case(caso)
        await db.commit()
        await db.refresh(interna)
    except Exception:
        await db.rollback()
        raise
    return interna, casos_internos


async def listar_funcoes_internas(
    activity_id: UUID, professor: Usuario, db: AsyncSession
) -> tuple[list[FuncaoAtividade], list[CasoTesteAtividade]]:
    await obter_atividade(activity_id, professor, db)
    repository = ActivityFunctionRepository(db)
    funcoes = await repository.list_functions(activity_id)
    casos = await repository.list_cases([funcao.uuid for funcao in funcoes])
    return funcoes, casos


async def remover_funcao_interna(
    activity_id: UUID, activity_function_id: UUID, professor: Usuario, db: AsyncSession
) -> None:
    atividade = await obter_atividade(activity_id, professor, db)
    _require_draft(atividade)
    repository = ActivityFunctionRepository(db)
    funcao = await repository.get_function(activity_function_id)
    if funcao is None or funcao.atividade_uuid != atividade.uuid:
        raise NotFoundError("Função da atividade")
    await repository.delete_function(funcao)
    await db.commit()


async def reordenar_funcoes_internas(
    activity_id: UUID,
    dados: ReordenarFuncoesAtividadeRequest,
    professor: Usuario,
    db: AsyncSession,
) -> list[FuncaoAtividade]:
    atividade = await obter_atividade(activity_id, professor, db)
    _require_draft(atividade)
    repository = ActivityFunctionRepository(db)
    funcoes = await repository.list_functions(atividade.uuid)
    expected_ids = {funcao.uuid for funcao in funcoes}
    requested_ids = dados.funcoes_atividade_uuid
    if len(requested_ids) != len(expected_ids) or set(requested_ids) != expected_ids:
        raise CodelabException("A ordenação deve conter exatamente as funções da atividade.", 422)
    by_id = {funcao.uuid: funcao for funcao in funcoes}
    ordered = [by_id[function_id] for function_id in requested_ids]
    for index, funcao in enumerate(ordered, start=1):
        funcao.ordem = -index
    await db.flush()
    for index, funcao in enumerate(ordered, start=1):
        funcao.ordem = index
    await db.commit()
    return ordered


async def publicar_atividade(activity_id: UUID, professor: Usuario, db: AsyncSession) -> Atividade:
    atividade = await obter_atividade(activity_id, professor, db)
    if atividade.status != "RASCUNHO":
        raise CodelabException("Somente atividades em rascunho podem ser publicadas.", 409)

    repository = ActivityFunctionRepository(db)
    funcoes = await repository.list_functions(atividade.uuid)
    if not funcoes:
        raise CodelabException("A atividade precisa ter ao menos uma função.", 422)

    casos = await repository.list_cases([funcao.uuid for funcao in funcoes])
    funcoes_com_caso = {caso.funcao_atividade_uuid for caso in casos}
    if any(funcao.uuid not in funcoes_com_caso for funcao in funcoes):
        raise CodelabException("Todas as funções da atividade precisam ter ao menos um caso de teste.", 422)

    total = sum((Decimal(funcao.nota_maxima) for funcao in funcoes), Decimal("0"))
    if total != Decimal("10"):
        raise CodelabException("A soma das notas máximas deve totalizar 10.", 422)

    atividade.status = "PUBLICADA"
    await db.commit()
    await db.refresh(atividade)
    return atividade


async def encerrar_atividade(activity_id: UUID, professor: Usuario, db: AsyncSession) -> Atividade:
    atividade = await obter_atividade(activity_id, professor, db)
    if atividade.status != "PUBLICADA":
        raise CodelabException("Somente atividades publicadas podem ser encerradas.", 409)
    atividade.status = "ENCERRADA"
    await db.commit()
    await db.refresh(atividade)
    return atividade


def atividade_aceita_submissoes(atividade: Atividade, agora: datetime | None = None) -> bool:
    agora = agora or datetime.now(timezone.utc)
    return atividade.status == "PUBLICADA" and atividade.inicio_em <= agora < atividade.fim_em
