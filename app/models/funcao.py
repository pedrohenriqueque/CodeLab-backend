import uuid

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class FuncaoBiblioteca(Base):
    __tablename__ = "funcoes_biblioteca"

    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    professor_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.uuid", ondelete="RESTRICT"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    enunciado: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_retorno: Mapped[str] = mapped_column(String(32), nullable=False)
    parametros: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    dificuldade: Mapped[str] = mapped_column(String(16), nullable=False)
    compartilhada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    professor: Mapped["Usuario"] = relationship("Usuario", lazy="joined")
