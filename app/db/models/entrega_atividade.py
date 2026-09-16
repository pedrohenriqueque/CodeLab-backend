"""Modelo: EntregaAtividade (RN14 - Entrega final consolidada da atividade)."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Numeric
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EntregaAtividade(Base):
    """
    Tabela de entrega final da atividade pelo aluno (RN14).
    
    A entrega final não envia novo código; ela consolida as notas das funções
    e encerra formalmente as tentativas do aluno para aquela atividade.
    """
    __tablename__ = "entregas_atividades"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    aluno_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("usuarios.uuid"), nullable=False
    )
    atividade_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("atividades.uuid", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        SAEnum("entregue", "cancelado", name="status_entrega_atividade"),
        nullable=False,
        default="entregue",
    )
    nota_final: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    data_entrega: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relacionamentos
    aluno = relationship("Usuario", back_populates="entregas_atividades")
    atividade = relationship("Atividade", back_populates="entregas_atividades")

    def __repr__(self):
        return f"<EntregaAtividade aluno={self.aluno_uuid[:8]} atv={self.atividade_uuid[:8]} status={self.status}>"
