from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from ..models.tentativa import ResultadoCasoTentativa, Tentativa
from ..models.funcao_atividade import FuncaoAtividade
from ..models.atividade import Atividade
from ..models.turma import MatriculaTurma, Turma
from ..models.usuario import Usuario


class SubmissionRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def list_summaries(
        self, *, student_id: UUID | None = None, professor_id: UUID | None = None,
        class_id: UUID | None = None, activity_id: UUID | None = None,
        function_id: UUID | None = None, filter_student_id: UUID | None = None,
    ) -> list:
        query = (
            select(
                Tentativa, FuncaoAtividade, Atividade, Usuario,
                func.row_number().over(
                    partition_by=(Tentativa.aluno_uuid, Tentativa.funcao_atividade_uuid),
                    order_by=(Tentativa.recebida_em, Tentativa.uuid),
                ).label("tentativa_numero"),
            )
            .join(FuncaoAtividade, Tentativa.funcao_atividade_uuid == FuncaoAtividade.uuid)
            .join(Atividade, FuncaoAtividade.atividade_uuid == Atividade.uuid)
            .join(Turma, Atividade.turma_uuid == Turma.uuid)
            .join(Usuario, Tentativa.aluno_uuid == Usuario.uuid)
            .options(
                load_only(Tentativa.uuid, Tentativa.aluno_uuid, Tentativa.funcao_atividade_uuid,
                          Tentativa.recebida_em, Tentativa.avaliada_em, Tentativa.status,
                          Tentativa.nota, Tentativa.total_casos, Tentativa.casos_aprovados),
                load_only(FuncaoAtividade.uuid, FuncaoAtividade.nome, FuncaoAtividade.nota_maxima),
                load_only(Usuario.uuid, Usuario.nome, Usuario.matricula),
            )
        )
        if student_id is not None:
            query = query.join(
                MatriculaTurma, MatriculaTurma.turma_uuid == Turma.uuid,
            ).where(MatriculaTurma.aluno_uuid == student_id, Tentativa.aluno_uuid == student_id,
                    Atividade.status != "RASCUNHO")
        elif professor_id is not None:
            query = query.where(Turma.professor_uuid == professor_id)
        else:
            raise ValueError("Informe o escopo autorizado da consulta.")
        for column, value in (
            (Atividade.turma_uuid, class_id), (Atividade.uuid, activity_id),
            (Tentativa.funcao_atividade_uuid, function_id), (Tentativa.aluno_uuid, filter_student_id),
        ):
            if value is not None:
                query = query.where(column == value)
        result = await self._db.execute(query.order_by(Tentativa.recebida_em.desc(), Tentativa.uuid.desc()))
        return list(result)

    async def list_for_student_functions(self, student_id: UUID, function_ids: list[UUID]) -> list[Tentativa]:
        if not function_ids:
            return []
        result = await self._db.scalars(
            select(Tentativa).where(
                Tentativa.aluno_uuid == student_id, Tentativa.funcao_atividade_uuid.in_(function_ids),
            ).options(load_only(
                Tentativa.uuid, Tentativa.funcao_atividade_uuid, Tentativa.recebida_em,
                Tentativa.status, Tentativa.nota,
            )).order_by(Tentativa.recebida_em.desc(), Tentativa.uuid.desc())
        )
        return list(result)

    async def count_by_activity_ids(self, activity_ids: list[UUID]) -> dict[UUID, int]:
        if not activity_ids:
            return {}
        result = await self._db.execute(
            select(FuncaoAtividade.atividade_uuid, func.count(Tentativa.uuid))
            .join(Tentativa, Tentativa.funcao_atividade_uuid == FuncaoAtividade.uuid)
            .where(FuncaoAtividade.atividade_uuid.in_(activity_ids))
            .group_by(FuncaoAtividade.atividade_uuid)
        )
        return dict(result.all())

    async def add(self, tentativa: Tentativa) -> None:
        self._db.add(tentativa)

    async def add_case_results(self, results: list[ResultadoCasoTentativa]) -> None:
        self._db.add_all(results)

    async def list_case_results(self, attempt_id: UUID) -> list[ResultadoCasoTentativa]:
        result = await self._db.scalars(
            select(ResultadoCasoTentativa).where(ResultadoCasoTentativa.tentativa_uuid == attempt_id)
        )
        return list(result)

    async def get_by_uuid(self, attempt_id: UUID) -> Tentativa | None:
        return await self._db.get(Tentativa, attempt_id)

    async def list_by_student(self, student_id: UUID) -> list[Tentativa]:
        result = await self._db.scalars(
            select(Tentativa).where(Tentativa.aluno_uuid == student_id).order_by(Tentativa.recebida_em.desc())
        )
        return list(result)

    async def count_consumed_attempts(
        self, function_id: UUID, student_id: UUID, *, is_prova: bool = False
    ) -> int:
        query = select(func.count()).select_from(Tentativa).where(
            Tentativa.funcao_atividade_uuid == function_id,
            Tentativa.aluno_uuid == student_id,
            Tentativa.status != "FALHA_TECNICA",
        )
        if is_prova:
            query = query.where(Tentativa.status != "ERRO_COMPILACAO")
        return await self._db.scalar(query) or 0

    async def list_by_professor(self, professor_id: UUID) -> list[Tentativa]:
        result = await self._db.scalars(
            select(Tentativa)
            .join(FuncaoAtividade, Tentativa.funcao_atividade_uuid == FuncaoAtividade.uuid)
            .join(Atividade, FuncaoAtividade.atividade_uuid == Atividade.uuid)
            .join(Turma, Atividade.turma_uuid == Turma.uuid)
            .where(Turma.professor_uuid == professor_id)
            .order_by(Tentativa.recebida_em.desc())
        )
        return list(result)

    async def best_score(self, function_id: UUID, student_id: UUID) -> Decimal | None:
        return await self._db.scalar(
            select(func.max(Tentativa.nota)).where(
                Tentativa.funcao_atividade_uuid == function_id,
                Tentativa.aluno_uuid == student_id,
                Tentativa.nota.is_not(None),
            )
        )

    async def list_by_class(self, class_id: UUID) -> list[Tentativa]:
        result = await self._db.scalars(
            select(Tentativa)
            .join(FuncaoAtividade, Tentativa.funcao_atividade_uuid == FuncaoAtividade.uuid)
            .join(Atividade, FuncaoAtividade.atividade_uuid == Atividade.uuid)
            .where(Atividade.turma_uuid == class_id)
        )
        return list(result)
