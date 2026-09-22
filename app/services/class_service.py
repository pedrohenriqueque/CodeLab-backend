"""Gestão de turmas e matrículas com autorização contextual."""

import secrets
import string
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import CodelabException, NotFoundError
from ..models.turma import MatriculaTurma, Turma
from ..models.usuario import PerfilUsuario, Usuario
from ..repositories.class_repository import ClassRepository
from ..repositories.enrollment_repository import EnrollmentRepository
from ..schemas.turma import AtualizarTurmaRequest, CriarTurmaRequest, IngressarTurmaRequest


def generate_class_code() -> str:
    return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))


def _require_profile(usuario: Usuario, perfil: PerfilUsuario) -> None:
    if usuario.perfil != perfil:
        raise CodelabException("Operação não permitida para este perfil.", status_code=403)


async def criar_turma(dados: CriarTurmaRequest, professor: Usuario, db: AsyncSession) -> Turma:
    _require_profile(professor, PerfilUsuario.PROFESSOR)
    nome = dados.nome.strip()
    if not nome:
        raise CodelabException("Nome da turma é obrigatório.", status_code=422)
    repository = ClassRepository(db)
    for _ in range(5):
        turma = Turma(nome=nome, codigo=generate_class_code(), professor_uuid=professor.uuid)
        await repository.add(turma)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            continue
        await db.refresh(turma)
        turma.total_alunos = 0
        turma.total_atividades = 0
        return turma
    raise CodelabException("Não foi possível gerar um código de turma.", status_code=500)


async def listar_turmas(usuario: Usuario, db: AsyncSession) -> list[Turma]:
    repository = ClassRepository(db)
    if usuario.perfil == PerfilUsuario.PROFESSOR:
        turmas = await repository.list_by_professor(usuario.uuid)
    elif usuario.perfil == PerfilUsuario.ALUNO:
        turmas = await repository.list_by_student(usuario.uuid)
    else:
        raise CodelabException("Operação não permitida para este perfil.", status_code=403)

    if turmas:
        turma_ids = [t.uuid for t in turmas]
        counts = await repository.get_turma_counts(turma_ids)
        for t in turmas:
            c = counts.get(t.uuid, {})
            t.total_alunos = c.get("total_alunos", 0)
            t.total_atividades = c.get("total_atividades", 0)
            if "inicio_aulas" in c:
                t.inicio_aulas = c["inicio_aulas"]
    return turmas


async def atualizar_turma(
    turma_id: UUID, dados: AtualizarTurmaRequest, professor: Usuario, db: AsyncSession
) -> Turma:
    _require_profile(professor, PerfilUsuario.PROFESSOR)
    turma = await ClassRepository(db).get_by_uuid(turma_id)
    if turma is None:
        raise NotFoundError("Turma")
    if turma.professor_uuid != professor.uuid:
        raise CodelabException("Você não gerencia esta turma.", status_code=403)
    if dados.nome is not None:
        nome = dados.nome.strip()
        if not nome:
            raise CodelabException("Nome da turma é obrigatório.", status_code=422)
        turma.nome = nome
    if dados.ativa is not None:
        turma.ativa = dados.ativa
    await db.commit()
    await db.refresh(turma)
    return turma


async def listar_alunos_turma(turma_id: UUID, professor: Usuario, db: AsyncSession) -> list[Usuario]:
    _require_profile(professor, PerfilUsuario.PROFESSOR)
    turma = await ClassRepository(db).get_by_uuid(turma_id)
    if turma is None:
        raise NotFoundError("Turma")
    if turma.professor_uuid != professor.uuid:
        raise CodelabException("Voc\u00ea n\u00e3o gerencia esta turma.", status_code=403)
    return await EnrollmentRepository(db).list_students(turma_id)


async def remover_aluno_turma(turma_id: UUID, aluno_id: UUID, professor: Usuario, db: AsyncSession) -> None:
    _require_profile(professor, PerfilUsuario.PROFESSOR)
    turma = await ClassRepository(db).get_by_uuid(turma_id)
    if turma is None:
        raise NotFoundError("Turma")
    if turma.professor_uuid != professor.uuid:
        raise CodelabException("Você não gerencia esta turma.", status_code=403)
    if not await EnrollmentRepository(db).remove(turma_id, aluno_id):
        raise NotFoundError("Matrícula")
    await db.commit()


async def ingressar_na_turma(
    dados: IngressarTurmaRequest, aluno: Usuario, db: AsyncSession
) -> Turma:
    _require_profile(aluno, PerfilUsuario.ALUNO)
    turma = await ClassRepository(db).get_by_code(dados.codigo.strip().upper())
    if turma is None:
        raise NotFoundError("Turma")
    if not turma.ativa:
        raise CodelabException("Turma inativa não aceita novas matrículas.", status_code=409)
    enrollments = EnrollmentRepository(db)
    if await enrollments.exists(turma.uuid, aluno.uuid):
        raise CodelabException("Aluno já está matriculado nesta turma.", status_code=409)
    await enrollments.add(MatriculaTurma(turma_uuid=turma.uuid, aluno_uuid=aluno.uuid))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise CodelabException("Aluno já está matriculado nesta turma.", status_code=409) from None
    return turma

async def listar_alunos_com_metricas(turma_id: UUID, professor: Usuario, db: AsyncSession) -> list[dict]:
    from collections import defaultdict
    from decimal import Decimal, ROUND_HALF_UP
    from ..repositories.activity_repository import ActivityRepository
    from ..repositories.activity_function_repository import ActivityFunctionRepository
    from ..repositories.submission_repository import SubmissionRepository

    alunos = await listar_alunos_turma(turma_id, professor, db)
    atividades = [item for item in await ActivityRepository(db).list_by_class_ids([turma_id]) if item.status != "RASCUNHO"]
    funcoes = []
    for atividade in atividades:
        funcoes.extend(await ActivityFunctionRepository(db).list_functions(atividade.uuid))
    atividade_por_funcao = {funcao.uuid: funcao.atividade_uuid for funcao in funcoes}
    tentativas = await SubmissionRepository(db).list_by_class(turma_id)
    resposta = []
    for aluno in alunos:
        tentativas_aluno = [item for item in tentativas if item.aluno_uuid == aluno.uuid and item.funcao_atividade_uuid in atividade_por_funcao]
        enviadas = {atividade_por_funcao[item.funcao_atividade_uuid] for item in tentativas_aluno}
        melhores = {}
        for item in tentativas_aluno:
            if item.nota is not None and (item.funcao_atividade_uuid not in melhores or item.nota > melhores[item.funcao_atividade_uuid]):
                melhores[item.funcao_atividade_uuid] = Decimal(item.nota)
        notas = defaultdict(lambda: Decimal("0"))
        for funcao_uuid, nota in melhores.items():
            notas[atividade_por_funcao[funcao_uuid]] += nota
        media = (sum(notas.values()) / len(notas)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if notas else None
        situacao = "Não iniciado" if not enviadas else "Em avaliação" if media is None else "Excelente" if media >= Decimal("7") else "Ativo" if media >= Decimal("5") else "Atenção"
        resposta.append({"uuid": aluno.uuid, "nome": aluno.nome, "email": aluno.email, "matricula": aluno.matricula, "atividades_enviadas": len(enviadas), "total_atividades": len(atividades), "media_nota": media, "situacao": situacao})
    return resposta


async def consultar_resultados_turma(turma_id: UUID, professor: Usuario, db: AsyncSession) -> dict:
    from decimal import Decimal, ROUND_HALF_UP
    from ..repositories.activity_repository import ActivityRepository
    from ..repositories.activity_function_repository import ActivityFunctionRepository
    from ..repositories.submission_repository import SubmissionRepository

    alunos = await listar_alunos_turma(turma_id, professor, db)
    atividades = [item for item in await ActivityRepository(db).list_by_class_ids([turma_id]) if item.status != "RASCUNHO"]
    funcoes = []
    for atividade in atividades:
        funcoes.extend(await ActivityFunctionRepository(db).list_functions(atividade.uuid))
    atividade_por_funcao = {funcao.uuid: funcao.atividade_uuid for funcao in funcoes}
    tentativas = await SubmissionRepository(db).list_by_class(turma_id)
    melhores = {}
    enviados = {}
    avaliadas = 0
    for tentativa in tentativas:
        atividade_uuid = atividade_por_funcao.get(tentativa.funcao_atividade_uuid)
        if atividade_uuid is None:
            continue
        enviados[(atividade_uuid, tentativa.aluno_uuid)] = True
        if tentativa.nota is None:
            continue
        avaliadas += 1
        chave = (atividade_uuid, tentativa.aluno_uuid, tentativa.funcao_atividade_uuid)
        if chave not in melhores or tentativa.nota > melhores[chave]:
            melhores[chave] = Decimal(tentativa.nota)
    notas_atividade_aluno = {}
    for (atividade_uuid, aluno_uuid, _), nota in melhores.items():
        chave = (atividade_uuid, aluno_uuid)
        notas_atividade_aluno[chave] = notas_atividade_aluno.get(chave, Decimal("0")) + nota
    todas_notas = list(notas_atividade_aluno.values())
    def media(notas):
        return (sum(notas) / len(notas)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if notas else None
    def aprovacao(notas, total_alunos):
        if total_alunos == 0:
            return None
        return (Decimal(sum(nota >= Decimal("7") for nota in notas)) * Decimal("100") / total_alunos).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    itens = []
    for atividade in atividades:
        notas = [nota for (atividade_uuid, _), nota in notas_atividade_aluno.items() if atividade_uuid == atividade.uuid]
        itens.append({"atividade_uuid": atividade.uuid, "titulo": atividade.titulo, "enviados": sum(1 for chave in enviados if chave[0] == atividade.uuid), "total_alunos": len(alunos), "media_nota": media(notas), "aprovacao_percentual": aprovacao(notas, len(alunos))})
    return {"media_geral": media(todas_notas), "aprovacao_percentual": aprovacao(todas_notas, len(alunos) * len(atividades)), "submissoes_avaliadas": avaliadas, "atividades": itens}
