"""Schemas Pydantic para CasoTeste."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from app.schemas.common import CAMEL_CONFIG


class CasoTesteCreate(BaseModel):
    """Request body para criar caso de teste."""
    model_config = CAMEL_CONFIG

    inputs: dict[str, Any] = Field(default_factory=dict)
    output_esperado: dict[str, Any] = Field(default_factory=dict)
    descricao: str | None = None


class CasoTesteResponse(BaseModel):
    """Response de caso de teste."""
    model_config = CAMEL_CONFIG

    uuid: str
    funcao_uuid: str
    numero: int
    inputs: dict[str, Any]
    output_esperado: dict[str, Any]
    descricao: str | None = None
    created_at: datetime | None = None
