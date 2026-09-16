"""Modelo: Funcao."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, JSON, Numeric
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Funcao(Base):
    """
    Tabela de funções C na Biblioteca Central do sistema.
    
    Funções existem de forma independente de qualquer atividade (RN01, RN02, RN04).
    Possuem uma dificuldade padrão na biblioteca (RN05) e são associadas a atividades
    por meio da entidade associativa AtividadeFuncao (RN07).
    """
    __tablename__ = "funcoes"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    nome_funcao: Mapped[str] = mapped_column(String(128), nullable=False)
    dificuldade_padrao: Mapped[str] = mapped_column(
        SAEnum("facil", "medio", "dificil", name="dificuldade_funcao"),
        nullable=False,
        default="medio",
    )
    parametros: Mapped[dict | list] = mapped_column(JSON, nullable=False, default=list)
    retorno: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_tentativas: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = ilimitado
    dicas: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list de strings, até 3

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relacionamentos
    atividades_funcoes = relationship(
        "AtividadeFuncao", back_populates="funcao", lazy="selectin",
        cascade="all, delete-orphan"
    )
    casos_teste = relationship(
        "CasoTeste", back_populates="funcao", lazy="selectin",
        cascade="all, delete-orphan"
    )
    submissoes = relationship(
        "Submissao", back_populates="funcao", lazy="selectin",
        cascade="all, delete-orphan"
    )

    # Propriedade de conveniência para acessar atividades associadas
    @property
    def atividades(self):
        return [af.atividade for af in self.atividades_funcoes]

    def __repr__(self):
        return f"<Funcao {self.nome_funcao} dificuldade_padrao={self.dificuldade_padrao}>"
