"""Modelo: Atividade."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, Numeric, Boolean
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Atividade(Base):
    """Tabela de atividades (listas de exercícios)."""
    __tablename__ = "atividades"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    professor_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("usuarios.uuid"), nullable=True  # nullable até ter auth
    )
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    pontuacao_maxima: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=100)
    data_abertura: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    data_fechamento: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum("rascunho", "publicado", "fechado", name="status_atividade"),
        nullable=False,
        default="rascunho",
    )
    tipo: Mapped[str] = mapped_column(
        SAEnum("exercicio", "prova", name="tipo_atividade"),
        nullable=False,
        default="exercicio",
    )
    notas_liberadas: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duracao_minutos: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = sem timer
    bloquear_paste: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relacionamentos
    professor = relationship("Usuario", back_populates="atividades")
    funcoes = relationship(
        "Funcao", back_populates="atividade", lazy="selectin",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Atividade {self.titulo}>"
