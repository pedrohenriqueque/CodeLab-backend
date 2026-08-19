"""Modelo: Submissao."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, JSON, Numeric
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Submissao(Base):
    """Tabela de submissões de código com resultado da avaliação."""
    __tablename__ = "submissoes"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    funcao_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("funcoes.uuid"), nullable=False
    )
    aluno_uuid: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("usuarios.uuid"), nullable=True  # nullable até ter auth
    )
    codigo_submetido: Mapped[str] = mapped_column(Text, nullable=False)
    data_submissao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    tentativa_numero: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        SAEnum("pendente", "compilando", "executando", "avaliado", "erro",
               name="status_submissao"),
        nullable=False,
        default="pendente",
    )
    nota: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    resultado_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    feedback_professor: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relacionamentos
    funcao = relationship("Funcao", back_populates="submissoes")
    aluno = relationship("Usuario", back_populates="submissoes")

    def __repr__(self):
        return f"<Submissao {self.uuid[:8]} status={self.status}>"
