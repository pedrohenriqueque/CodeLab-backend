from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.atividade import Atividade

class ActivityRepository:
    def __init__(self, db: AsyncSession): self._db = db
    async def add(self, atividade: Atividade) -> None: self._db.add(atividade)
    async def get_by_uuid(self, activity_id: UUID) -> Atividade | None: return await self._db.get(Atividade, activity_id)
    async def list_by_class_ids(self, class_ids: list[UUID]) -> list[Atividade]:
        if not class_ids: return []
        result = await self._db.scalars(select(Atividade).where(Atividade.turma_uuid.in_(class_ids)).order_by(Atividade.inicio_em))
        return list(result)
