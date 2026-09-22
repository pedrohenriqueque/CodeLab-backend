"""Persistência das matrículas de alunos em turmas."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.turma import MatriculaTurma
from ..models.usuario import Usuario


class EnrollmentRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def add(self, matricula: MatriculaTurma) -> None:
        self._db.add(matricula)

    async def exists(self, turma_id: UUID, aluno_id: UUID) -> bool:
        return await self._db.scalar(
            select(MatriculaTurma.uuid).where(
                MatriculaTurma.turma_uuid == turma_id,
                MatriculaTurma.aluno_uuid == aluno_id,
            )
        ) is not None

    async def list_students(self, turma_id: UUID) -> list[Usuario]:
        result = await self._db.scalars(
            select(Usuario)
            .join(MatriculaTurma, MatriculaTurma.aluno_uuid == Usuario.uuid)
            .where(MatriculaTurma.turma_uuid == turma_id)
            .order_by(Usuario.nome)
        )
        return list(result.all())

    async def remove(self, turma_id: UUID, aluno_id: UUID) -> bool:
        result = await self._db.execute(
            delete(MatriculaTurma).where(
                MatriculaTurma.turma_uuid == turma_id,
                MatriculaTurma.aluno_uuid == aluno_id,
            )
        )
        return bool(result.rowcount)
