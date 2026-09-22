import uuid
from enum import Enum

from sqlalchemy import Boolean, Enum as SqlEnum
from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PerfilUsuario(str, Enum):
    ADMIN = "ADMIN"
    PROFESSOR = "PROFESSOR"
    ALUNO = "ALUNO"


class Usuario(Base):
    __tablename__ = "usuarios"

    __table_args__ = (
        UniqueConstraint("email", name="uq_usuarios_email"),
        UniqueConstraint("matricula", name="uq_usuarios_matricula"),
    )

    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    matricula: Mapped[str | None] = mapped_column(String(50), nullable=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    perfil: Mapped[PerfilUsuario] = mapped_column(
        SqlEnum(PerfilUsuario, name="perfil_usuario"),
        nullable=False,
    )
