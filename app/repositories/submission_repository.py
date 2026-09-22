from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.tentativa import ResultadoCasoTentativa, Tentativa
from ..models.funcao_atividade import FuncaoAtividade
from ..models.atividade import Atividade
from ..models.turma import Turma


class SubmissionRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

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

    async def count_consumed_attempts(self, function_id: UUID, student_id: UUID) -> int:
        return await self._db.scalar(
            select(func.count()).select_from(Tentativa).where(
                Tentativa.funcao_atividade_uuid == function_id,
                Tentativa.aluno_uuid == student_id,
                Tentativa.status != "FALHA_TECNICA",
            )
        ) or 0

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