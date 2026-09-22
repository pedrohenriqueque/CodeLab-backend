"""Aceitação durável e avaliação de tentativas individuais."""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import CodelabException, NotFoundError
from ..models.tentativa import ResultadoCasoTentativa, Tentativa
from ..models.usuario import PerfilUsuario, Usuario
from ..repositories.activity_function_repository import ActivityFunctionRepository
from ..repositories.activity_repository import ActivityRepository
from ..repositories.enrollment_repository import EnrollmentRepository
from ..repositories.submission_repository import SubmissionRepository
from ..schemas.tentativa import CriarTentativaRequest
from .activity_service import atividade_aceita_submissoes
from .evaluation_service import CodeExecutor, EvaluationService
from .gerador_service import UnsupportedCSignatureError


async def criar_tentativa(
    dados: CriarTentativaRequest,
    aluno: Usuario,
    db: AsyncSession,
    executor: CodeExecutor,
) -> Tentativa:
    """Registra a tentativa recebida antes de iniciar a integração externa."""
    if aluno.perfil != PerfilUsuario.ALUNO:
        raise CodelabException("Somente alunos podem enviar tentativas.", 403)

    functions = ActivityFunctionRepository(db)
    funcao = await functions.get_function(dados.funcao_atividade_uuid)
    if funcao is None:
        raise NotFoundError("Função da atividade")

    atividade = await ActivityRepository(db).get_by_uuid(funcao.atividade_uuid)
    if atividade is None:
        raise NotFoundError("Atividade")
    if not await EnrollmentRepository(db).exists(atividade.turma_uuid, aluno.uuid):
        raise CodelabException("Você não está matriculado nesta turma.", 403)
    if not atividade_aceita_submissoes(atividade):
        raise CodelabException("A atividade não está aberta para submissões.", 409)

    limite = 1 if atividade.tipo == "PROVA" or not atividade.permitir_multiplas_submissoes else atividade.max_tentativas_por_funcao
    consumidas = await SubmissionRepository(db).count_consumed_attempts(funcao.uuid, aluno.uuid)
    if limite is not None and consumidas >= limite:
        raise CodelabException("O limite de tentativas para esta função foi atingido.", 409)

    casos = await functions.list_cases([funcao.uuid])
    if not casos:
        raise CodelabException("Funções sem casos de teste não podem ser avaliadas.", 422)
    recebida_em = datetime.now(timezone.utc)
    tentativa = Tentativa(
        funcao_atividade_uuid=funcao.uuid,
        aluno_uuid=aluno.uuid,
        codigo_fonte=dados.codigo_fonte,
        recebida_em=recebida_em,
        status="PROCESSANDO",
        total_casos=len(casos),
        casos_aprovados=0,
        nota=None,
    )
    await SubmissionRepository(db).add(tentativa)
    await db.commit()
    await db.refresh(tentativa)

    snapshot = {
        "nome": funcao.nome,
        "tipo_retorno": funcao.tipo_retorno,
        "parametros": funcao.parametros,
    }
    cases = [
        {"entradas": caso.entradas, "retorno_esperado": caso.retorno_esperado}
        for caso in casos
    ]
    try:
        resultado = await EvaluationService(executor).avaliar(snapshot, cases, dados.codigo_fonte)
    except UnsupportedCSignatureError as error:
        tentativa.status = "ASSINATURA_NAO_SUPORTADA"
        tentativa.avaliada_em = datetime.now(timezone.utc)
        await db.commit()
        raise CodelabException(str(error), 422) from None

    tentativa.status = (
        "FALHA_TECNICA" if resultado.technical_failure else
        "ERRO_COMPILACAO" if resultado.compilation_error else "AVALIADA"
    )
    tentativa.total_casos = resultado.total_cases
    tentativa.casos_aprovados = resultado.passed_cases
    if not resultado.technical_failure:
        tentativa.nota = calcular_nota(funcao.nota_maxima, resultado.passed_cases, resultado.total_cases)
        resultados_por_caso = resultado.case_results or tuple(False for _ in casos)
        await SubmissionRepository(db).add_case_results([
            ResultadoCasoTentativa(
                tentativa_uuid=tentativa.uuid,
                caso_teste_atividade_uuid=caso.uuid,
                aprovado=aprovado,
            )
            for caso, aprovado in zip(casos, resultados_por_caso, strict=True)
        ])
    tentativa.avaliada_em = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tentativa)
    return tentativa


def calcular_nota(nota_maxima: Decimal, casos_aprovados: int, total_casos: int) -> Decimal:
    """Calcula exclusivamente no backend a nota proporcional aprovada na DEC-02."""
    if total_casos <= 0:
        raise ValueError("Uma função avaliada precisa ter casos de teste.")
    nota = Decimal(nota_maxima) * Decimal(casos_aprovados) / Decimal(total_casos)
    return nota.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def resultado_liberado(atividade, agora: datetime | None = None) -> bool:
    """Indica quando resultados podem ser exibidos ao aluno."""
    if atividade.tipo != "PROVA" or atividade.status == "ENCERRADA":
        return True
    referencia = agora or datetime.now(timezone.utc)
    return referencia >= atividade.fim_em


async def resposta_tentativa(
    tentativa: Tentativa,
    db: AsyncSession,
    nota_maxima: Decimal,
    *,
    liberar_resultado: bool,
) -> dict[str, Any]:
    """Projeção mínima para o aluno; código e dados de casos não saem da API."""
    melhor_nota = None
    if liberar_resultado:
        melhor_nota = await SubmissionRepository(db).best_score(
            tentativa.funcao_atividade_uuid, tentativa.aluno_uuid
        )
    return {
        "uuid": tentativa.uuid,
        "funcao_atividade_uuid": tentativa.funcao_atividade_uuid,
        "recebida_em": tentativa.recebida_em,
        "avaliada_em": tentativa.avaliada_em,
        "status": tentativa.status if liberar_resultado else "ENVIO_REGISTRADO",
        "total_casos": tentativa.total_casos if liberar_resultado else None,
        "casos_aprovados": tentativa.casos_aprovados if liberar_resultado else None,
        "falha_tecnica": tentativa.status == "FALHA_TECNICA",
        "nota": tentativa.nota if liberar_resultado else None,
        "nota_maxima": nota_maxima,
        "melhor_nota_funcao": melhor_nota,
    }


async def consultar_tentativa(
    attempt_id,
    usuario: Usuario,
    db: AsyncSession,
    *,
    alunos_por_uuid: dict[UUID, Usuario] | None = None,
) -> dict[str, Any]:
    tentativa = await SubmissionRepository(db).get_by_uuid(attempt_id)
    if tentativa is None:
        raise NotFoundError("Tentativa")
    funcao = await ActivityFunctionRepository(db).get_function(tentativa.funcao_atividade_uuid)
    atividade = await ActivityRepository(db).get_by_uuid(funcao.atividade_uuid)
    professor = usuario.perfil == PerfilUsuario.PROFESSOR
    if usuario.perfil == PerfilUsuario.ALUNO:
        if tentativa.aluno_uuid != usuario.uuid:
            raise NotFoundError("Tentativa")
        if not await EnrollmentRepository(db).exists(atividade.turma_uuid, usuario.uuid):
            raise NotFoundError("Tentativa")
    elif professor:
        from ..repositories.class_repository import ClassRepository
        turma = await ClassRepository(db).get_by_uuid(atividade.turma_uuid)
        if turma is None or turma.professor_uuid != usuario.uuid:
            raise NotFoundError("Tentativa")
    else:
        raise CodelabException("Operação não permitida para este perfil.", 403)

    liberar = professor or resultado_liberado(atividade)
    data = {
        "uuid": tentativa.uuid, "funcao_atividade_uuid": funcao.uuid,
        "atividade_uuid": atividade.uuid, "atividade_titulo": atividade.titulo,
        "funcao_nome": funcao.nome, "recebida_em": tentativa.recebida_em,
        "status": tentativa.status if liberar else "ENVIO_REGISTRADO",
        "falha_tecnica": tentativa.status == "FALHA_TECNICA",
        "codigo_fonte": tentativa.codigo_fonte,
    }
    if liberar:
        data.update({"nota": tentativa.nota, "nota_maxima": funcao.nota_maxima,
                     "casos_aprovados": tentativa.casos_aprovados, "total_casos": tentativa.total_casos})
    if professor:
        aluno = (
            alunos_por_uuid.get(tentativa.aluno_uuid)
            if alunos_por_uuid is not None
            else await db.get(Usuario, tentativa.aluno_uuid)
        )
        data["aluno_nome"] = aluno.nome if aluno else None
        data["aluno_matricula"] = aluno.matricula if aluno else None
        resultados = {item.caso_teste_atividade_uuid: item.aprovado for item in await SubmissionRepository(db).list_case_results(tentativa.uuid)}
        casos = await ActivityFunctionRepository(db).list_cases([funcao.uuid])
        data["resultados_casos"] = [{"casoTesteAtividadeUuid": caso.uuid, "aprovado": resultados.get(caso.uuid, False), "entradas": caso.entradas, "retornoEsperado": caso.retorno_esperado, "visibilidade": caso.visibilidade} for caso in casos]
    return data


async def listar_tentativas(usuario: Usuario, db: AsyncSession) -> list[dict[str, Any]]:
    repository = SubmissionRepository(db)
    alunos_por_uuid = None
    if usuario.perfil == PerfilUsuario.ALUNO:
        tentativas = await repository.list_by_student(usuario.uuid)
    elif usuario.perfil == PerfilUsuario.PROFESSOR:
        tentativas = await repository.list_by_professor(usuario.uuid)
        alunos_por_uuid = {}
        if tentativas:
            alunos = await db.scalars(
                select(Usuario).where(Usuario.uuid.in_({tentativa.aluno_uuid for tentativa in tentativas}))
            )
            alunos_por_uuid = {aluno.uuid: aluno for aluno in alunos}
    else:
        raise CodelabException("Operação não permitida para este perfil.", 403)
    return [
        await consultar_tentativa(tentativa.uuid, usuario, db, alunos_por_uuid=alunos_por_uuid)
        for tentativa in tentativas
    ]
