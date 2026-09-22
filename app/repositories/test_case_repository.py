from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.caso_teste import CasoTeste


class TestCaseRepository:
    def __init__(self, db: AsyncSession): self._db = db

    async def add(self, caso: CasoTeste) -> None: self._db.add(caso)

    async def get_by_uuid(self, case_id: UUID) -> CasoTeste | None:
        return await self._db.get(CasoTeste, case_id)

    async def list_by_function(self, function_id: UUID) -> list[CasoTeste]:
        result = await self._db.scalars(select(CasoTeste).where(CasoTeste.funcao_uuid == function_id))
        return list(result)

    async def count_by_function_ids(self, function_ids: list[UUID]) -> dict[UUID, int]:
        if not function_ids:
            return {}
        result = await self._db.execute(
            select(CasoTeste.funcao_uuid, func.count(CasoTeste.uuid))
            .where(CasoTeste.funcao_uuid.in_(function_ids))
            .group_by(CasoTeste.funcao_uuid)
        )
        return {function_id: count for function_id, count in result.all()}

    async def delete(self, caso: CasoTeste) -> None: await self._db.delete(caso)
