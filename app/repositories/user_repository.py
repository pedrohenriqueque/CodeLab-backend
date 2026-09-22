"""Consultas e persistência de usuários, sem regras de autorização."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.usuario import PerfilUsuario, Usuario


class UserRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_email_or_matricula(
        self, *, email: str, matricula: str | None
    ) -> Usuario | None:
        return await self._db.scalar(
            select(Usuario).where(
                Usuario.email == email
                if matricula is None
                else or_(Usuario.email == email, Usuario.matricula == matricula)
            )
        )

    async def get_by_email(self, email: str) -> Usuario | None:
        return await self._db.scalar(
            select(Usuario).where(Usuario.email == email, Usuario.ativo.is_(True))
        )

    async def get_by_uuid(self, user_id: UUID) -> Usuario | None:
        usuario = await self._db.get(Usuario, user_id)
        return usuario if usuario is not None and getattr(usuario, "ativo", True) else None

    async def add(self, usuario: Usuario) -> None:
        self._db.add(usuario)

    async def count_admins(self) -> int:
        result = await self._db.scalar(
            select(func.count()).select_from(Usuario).where(
                Usuario.perfil == PerfilUsuario.ADMIN, Usuario.ativo.is_(True)
            )
        )
        return int(result or 0)

    async def list_professors(self) -> list[Usuario]:
        result = await self._db.scalars(
            select(Usuario)
            .where(Usuario.perfil == PerfilUsuario.PROFESSOR, Usuario.ativo.is_(True))
            .order_by(Usuario.nome)
        )
        return list(result)
