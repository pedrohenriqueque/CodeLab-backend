"""Modelo: Usuario."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Usuario(Base):
    """Tabela de usuários (professores e alunos)."""
    __tablename__ = "usuarios"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    tipo: Mapped[str] = mapped_column(
        SAEnum("professor", "aluno", name="tipo_usuario"),
        nullable=False,
    )
    senha_hash: Mapped[str] = mapped_column(String(256), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relacionamentos
    atividades = relationship("Atividade", back_populates="professor", lazy="selectin")
    submissoes = relationship("Submissao", back_populates="aluno", lazy="selectin")

    def __repr__(self):
        return f"<Usuario {self.nome} ({self.tipo})>"
