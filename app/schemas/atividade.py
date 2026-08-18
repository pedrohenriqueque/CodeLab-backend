"""Schemas Pydantic para Atividade."""

from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.common import CAMEL_CONFIG
from app.schemas.funcao import FuncaoResponse


class AtividadeCreate(BaseModel):
    """Request body para criar atividade."""
    model_config = CAMEL_CONFIG

    titulo: str = Field(..., min_length=1, max_length=300)
    descricao: str | None = None
    pontuacao_maxima: float = 100
    data_abertura: datetime | None = None
    data_fechamento: datetime | None = None
    status: str = "rascunho"
    tipo: str = "exercicio"
    duracao_minutos: int | None = None
    bloquear_paste: bool = False
    notas_liberadas: bool = False


class AtividadeUpdate(BaseModel):
    """Request body para atualizar atividade (PATCH — campos opcionais)."""
    model_config = CAMEL_CONFIG

    titulo: str | None = None
    descricao: str | None = None
    pontuacao_maxima: float | None = None
    data_abertura: datetime | None = None
    data_fechamento: datetime | None = None
    status: str | None = None
    tipo: str | None = None
    duracao_minutos: int | None = None
    bloquear_paste: bool | None = None
    notas_liberadas: bool | None = None


class AtividadeResponse(BaseModel):
    """Response de atividade."""
    model_config = CAMEL_CONFIG

    uuid: str
    professor_uuid: str | None = None
    titulo: str
    descricao: str | None = None
    pontuacao_maxima: float
    data_abertura: datetime | None = None
    data_fechamento: datetime | None = None
    status: str
    tipo: str
    duracao_minutos: int | None = None
    bloquear_paste: bool = False
    notas_liberadas: bool = False
    created_at: datetime | None = None
    funcoes: list[FuncaoResponse] = []
