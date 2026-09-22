"""Persistência de turmas, sem regras de autorização."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.turma import MatriculaTurma, Turma


class ClassRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def add(self, turma: Turma) -> None:
        self._db.add(turma)

    async def get_by_uuid(self, turma_id: UUID) -> Turma | None:
        return await self._db.get(Turma, turma_id)

    async def get_by_code(self, codigo: str) -> Turma | None:
        return await self._db.scalar(select(Turma).where(Turma.codigo == codigo))

    async def list_by_professor(self, professor_id: UUID) -> list[Turma]:
        result = await self._db.scalars(
            select(Turma).where(Turma.professor_uuid == professor_id).order_by(Turma.nome)
        )
        return list(result)

    async def list_by_student(self, aluno_id: UUID) -> list[Turma]:
        result = await self._db.scalars(
            select(Turma)
            .join(MatriculaTurma, MatriculaTurma.turma_uuid == Turma.uuid)
            .where(MatriculaTurma.aluno_uuid == aluno_id)
            .order_by(Turma.nome)
        )
        return list(result)

    async def get_turma_counts(self, class_ids: list[UUID]) -> dict[UUID, dict[str, int]]:
        if not class_ids:
            return {}
        from sqlalchemy import func
        from ..models.atividade import Atividade

        counts: dict[UUID, dict[str, int]] = {
            cid: {"total_alunos": 0, "total_atividades": 0} for cid in class_ids
        }

        stmt_alunos = (
            select(MatriculaTurma.turma_uuid, func.count(MatriculaTurma.uuid))
            .where(MatriculaTurma.turma_uuid.in_(class_ids))
            .group_by(MatriculaTurma.turma_uuid)
        )
        res_alunos = await self._db.execute(stmt_alunos)
        for turma_id, count in res_alunos:
            if turma_id in counts:
                counts[turma_id]["total_alunos"] = count

        stmt_atividades = (
            select(
                Atividade.turma_uuid,
                func.count(Atividade.uuid),
                func.min(Atividade.inicio_em),
            )
            .where(Atividade.turma_uuid.in_(class_ids))
            .group_by(Atividade.turma_uuid)
        )
        res_atividades = await self._db.execute(stmt_atividades)
        for turma_id, count, min_inicio in res_atividades:
            if turma_id in counts:
                counts[turma_id]["total_atividades"] = count
                if min_inicio is not None:
                    counts[turma_id]["inicio_aulas"] = min_inicio.strftime("%d/%m/%Y")

        return counts
