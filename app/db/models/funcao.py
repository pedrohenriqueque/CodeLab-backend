"""Modelo: Funcao."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, JSON, Numeric
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Funcao(Base):
    """Tabela de funções C a serem implementadas pelos alunos."""
    __tablename__ = "funcoes"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    atividade_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("atividades.uuid", ondelete="CASCADE"), nullable=False
    )
    nome_funcao: Mapped[str] = mapped_column(String(128), nullable=False)
    pontos: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=10)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parametros: Mapped[dict | list] = mapped_column(JSON, nullable=False, default=list)
    retorno: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    dificuldade: Mapped[str] = mapped_column(
        SAEnum("facil", "medio", "dificil", name="dificuldade_funcao"),
        nullable=False,
        default="medio",
    )
    max_tentativas: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = ilimitado
    dicas: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list de strings, até 3

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relacionamentos
    atividade = relationship("Atividade", back_populates="funcoes")
    casos_teste = relationship(
        "CasoTeste", back_populates="funcao", lazy="selectin",
        cascade="all, delete-orphan"
    )
    submissoes = relationship(
        "Submissao", back_populates="funcao", lazy="selectin",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Funcao {self.nome_funcao}>"
