import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Turma(Base):
    __tablename__ = "turmas"

    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    codigo: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    professor_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.uuid", ondelete="RESTRICT"), nullable=False
    )


class MatriculaTurma(Base):
    __tablename__ = "matriculas_turma"
    __table_args__ = (
        UniqueConstraint("turma_uuid", "aluno_uuid", name="uq_matriculas_turma_aluno"),
    )

    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    turma_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("turmas.uuid", ondelete="CASCADE"), nullable=False
    )
    aluno_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.uuid", ondelete="RESTRICT"), nullable=False
    )
