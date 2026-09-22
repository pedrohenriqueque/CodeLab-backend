import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Atividade(Base):
    __tablename__ = "atividades"
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    turma_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("turmas.uuid", ondelete="RESTRICT"), nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False, default="")
    inicio_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fim_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RASCUNHO")
    tipo: Mapped[str] = mapped_column(String(16), nullable=False, default="EXERCICIO")
    permitir_multiplas_submissoes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_tentativas_por_funcao: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mostrar_ocultos_apos_fechamento: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
