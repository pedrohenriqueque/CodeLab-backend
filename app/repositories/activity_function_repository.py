from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.funcao_atividade import CasoTesteAtividade, FuncaoAtividade


class ActivityFunctionRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def add_function(self, funcao: FuncaoAtividade) -> None:
        self._db.add(funcao)

    async def add_case(self, caso: CasoTesteAtividade) -> None:
        self._db.add(caso)

    async def get_function(self, function_id: UUID) -> FuncaoAtividade | None:
        return await self._db.get(FuncaoAtividade, function_id)

    async def list_functions(self, activity_id: UUID) -> list[FuncaoAtividade]:
        result = await self._db.scalars(
            select(FuncaoAtividade)
            .where(FuncaoAtividade.atividade_uuid == activity_id)
            .order_by(FuncaoAtividade.ordem)
        )
        return list(result)

    async def list_cases(self, activity_function_ids: list[UUID]) -> list[CasoTesteAtividade]:
        if not activity_function_ids:
            return []
        result = await self._db.scalars(
            select(CasoTesteAtividade).where(CasoTesteAtividade.funcao_atividade_uuid.in_(activity_function_ids))
        )
        return list(result)

    async def next_order(self, activity_id: UUID) -> int:
        current = await self._db.scalar(
            select(func.max(FuncaoAtividade.ordem)).where(FuncaoAtividade.atividade_uuid == activity_id)
        )
        return (current or 0) + 1

    async def delete_function(self, funcao: FuncaoAtividade) -> None:
        await self._db.delete(funcao)
