"""Schemas Pydantic para Submissao."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from app.schemas.common import CAMEL_CONFIG


class SubmissaoCreate(BaseModel):
    """Request body para submeter código."""
    model_config = CAMEL_CONFIG

    funcao_uuid: str
    atividade_uuid: str | None = None
    codigo: str = Field(..., min_length=1)


class CasoResultado(BaseModel):
    """Resultado individual de um caso de teste."""
    model_config = CAMEL_CONFIG

    numero: int
    status: str  # "PASS" ou "FAIL"
    expected: str | None = None
    got: str | None = None


class SubmissaoResponse(BaseModel):
    """Response completa de uma submissão avaliada."""
    model_config = CAMEL_CONFIG

    submissao_uuid: str
    funcao: str
    nota: float
    pontos_maximo: float
    total_casos: int
    casos_passados: int
    casos: list[CasoResultado]
    erro_compilacao: str | None = None
    erro_execucao: str | None = None
    tempo_ms: float = 0.0
    memoria_kb: int = 0


class SubmissaoListResponse(BaseModel):
    """Response resumida para listagem."""
    model_config = CAMEL_CONFIG

    uuid: str
    funcao_uuid: str
    funcao_nome: str | None = None
    atividade_uuid: str | None = None
    atividade_titulo: str | None = None
    aluno_nome: str | None = None
    codigo_submetido: str | None = None
    data_submissao: datetime | None = None
    tentativa_numero: int
    status: str
    nota: float | None = None
    pontos_total: float | None = None
    resultado_json: dict[str, Any] | None = None
    feedback_professor: str | None = None

class SubmissaoFeedbackUpdate(BaseModel):
    """Request body para atualizar o feedback do professor."""
    model_config = CAMEL_CONFIG

    feedback_professor: str | None = None
