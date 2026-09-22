import uuid

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CasoTeste(Base):
    __tablename__ = "casos_teste"

    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    funcao_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("funcoes_biblioteca.uuid", ondelete="CASCADE"), nullable=False
    )
    entradas: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    retorno_esperado: Mapped[object] = mapped_column(JSON, nullable=False)
    visibilidade: Mapped[str] = mapped_column(String(16), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False, default="")
