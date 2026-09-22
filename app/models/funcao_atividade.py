import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class FuncaoAtividade(Base):
    __tablename__ = "funcoes_atividade"
    __table_args__ = (UniqueConstraint("atividade_uuid", "ordem", name="uq_funcoes_atividade_ordem"),)

    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    atividade_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("atividades.uuid", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    enunciado: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_retorno: Mapped[str] = mapped_column(String(32), nullable=False)
    parametros: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    dificuldade: Mapped[str] = mapped_column(String(16), nullable=False)
    nota_maxima: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)


class CasoTesteAtividade(Base):
    __tablename__ = "casos_teste_atividade"

    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    funcao_atividade_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("funcoes_atividade.uuid", ondelete="CASCADE"), nullable=False
    )
    entradas: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    retorno_esperado: Mapped[object] = mapped_column(JSON, nullable=False)
    visibilidade: Mapped[str] = mapped_column(String(16), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False, default="")
