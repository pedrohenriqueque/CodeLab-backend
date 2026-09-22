from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ..models.funcao import FuncaoBiblioteca


class FunctionRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def add(self, funcao: FuncaoBiblioteca) -> None:
        self._db.add(funcao)

    async def get_by_uuid(self, function_id: UUID) -> FuncaoBiblioteca | None:
        return await self._db.scalar(
            select(FuncaoBiblioteca)
            .options(joinedload(FuncaoBiblioteca.professor))
            .where(FuncaoBiblioteca.uuid == function_id)
        )

    async def list_visible_to(self, professor_id: UUID) -> list[FuncaoBiblioteca]:
        result = await self._db.scalars(
            select(FuncaoBiblioteca)
            .options(joinedload(FuncaoBiblioteca.professor))
            .where(or_(FuncaoBiblioteca.professor_uuid == professor_id, FuncaoBiblioteca.compartilhada.is_(True)))
            .order_by(FuncaoBiblioteca.nome)
        )
        return list(result)

    async def delete(self, funcao: FuncaoBiblioteca) -> None:
        await self._db.delete(funcao)
