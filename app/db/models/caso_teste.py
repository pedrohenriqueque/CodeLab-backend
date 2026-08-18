"""Modelo: CasoTeste."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class CasoTeste(Base):
    """Tabela de casos de teste vinculados a uma função."""
    __tablename__ = "casos_teste"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    funcao_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("funcoes.uuid", ondelete="CASCADE"), nullable=False
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    inputs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_esperado: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    descricao: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relacionamentos
    funcao = relationship("Funcao", back_populates="casos_teste")

    def __repr__(self):
        return f"<CasoTeste {self.numero} funcao={self.funcao_uuid[:8]}>"
