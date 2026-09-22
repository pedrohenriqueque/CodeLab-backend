import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Tentativa(Base):
    """Uma submissão imutável de um aluno para uma função interna."""

    __tablename__ = "tentativas"

    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    funcao_atividade_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("funcoes_atividade.uuid", ondelete="RESTRICT"), nullable=False
    )
    aluno_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.uuid", ondelete="RESTRICT"), nullable=False
    )
    codigo_fonte: Mapped[str] = mapped_column(Text, nullable=False)
    recebida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    avaliada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    total_casos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    casos_aprovados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nota: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)


class ResultadoCasoTentativa(Base):
    __tablename__ = "resultados_casos_tentativa"

    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tentativa_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tentativas.uuid", ondelete="CASCADE"), nullable=False
    )
    caso_teste_atividade_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("casos_teste_atividade.uuid", ondelete="RESTRICT"), nullable=False
    )
    aprovado: Mapped[bool] = mapped_column(Boolean, nullable=False)
