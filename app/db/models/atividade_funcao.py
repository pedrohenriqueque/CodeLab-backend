"""Modelo associativo: AtividadeFuncao e configuração contextual de casos de teste."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, ForeignKey, Numeric, Boolean
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AtividadeFuncao(Base):
    """
    Tabela associativa N:N entre Atividade e Funcao.
    
    Armazena a utilização e parametrização contextual de uma função
    dentro de uma atividade específica.
    """
    __tablename__ = "atividades_funcoes"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    atividade_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("atividades.uuid", ondelete="CASCADE"), nullable=False
    )
    funcao_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("funcoes.uuid", ondelete="CASCADE"), nullable=False
    )
    dificuldade: Mapped[str] = mapped_column(
        SAEnum("facil", "medio", "dificil", name="dificuldade_funcao"),
        nullable=False,
        default="medio",
    )
    peso: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=10)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relacionamentos
    atividade = relationship("Atividade", back_populates="atividades_funcoes")
    funcao = relationship("Funcao", back_populates="atividades_funcoes")
    casos_teste_config = relationship(
        "AtividadeFuncaoCasoTeste",
        back_populates="atividade_funcao",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<AtividadeFuncao atv={self.atividade_uuid[:8]} func={self.funcao_uuid[:8]}>"


class AtividadeFuncaoCasoTeste(Base):
    """
    Configuração contextual dos casos de teste selecionados para uma função na atividade.
    
    Permite definir quais casos de teste canônicos da função serão executados
    na atividade e sua visibilidade individual (oculto ou visível).
    """
    __tablename__ = "atividades_funcoes_casos_teste"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    atividade_funcao_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("atividades_funcoes.uuid", ondelete="CASCADE"), nullable=False
    )
    caso_teste_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("casos_teste.uuid", ondelete="CASCADE"), nullable=False
    )
    oculto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relacionamentos
    atividade_funcao = relationship("AtividadeFuncao", back_populates="casos_teste_config")
    caso_teste = relationship("CasoTeste", lazy="selectin")

    def __repr__(self):
        return f"<AtividadeFuncaoCasoTeste caso={self.caso_teste_uuid[:8]} oculto={self.oculto}>"
