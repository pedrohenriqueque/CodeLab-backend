"""Schemas Pydantic para Funcao."""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any
from app.schemas.common import CAMEL_CONFIG
from app.schemas.caso_teste import CasoTesteResponse


class ParametroSchema(BaseModel):
    """Schema para um parâmetro de função C."""
    model_config = CAMEL_CONFIG

    nome: str
    tipo: str = "int"


class RetornoSchema(BaseModel):
    """Schema para o tipo de retorno de uma função C."""
    model_config = CAMEL_CONFIG

    tipo: str = "int"


class FuncaoCreate(BaseModel):
    """Request body para criar função."""
    model_config = CAMEL_CONFIG

    nome_funcao: str = Field(..., min_length=1, max_length=128, pattern=r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    pontos: float = 10
    ordem: int = 0
    parametros: list[ParametroSchema] = [ParametroSchema(nome="a", tipo="int")]
    retorno: RetornoSchema = RetornoSchema(tipo="int")
    descricao: str | None = None
    dificuldade: str = "medio"  # facil | medio | dificil
    max_tentativas: int | None = None  # None = ilimitado
    dicas: list[str] | None = None  # até 3 dicas progressivas


class FuncaoResponse(BaseModel):
    """Response de função."""
    model_config = CAMEL_CONFIG

    uuid: str
    atividade_uuid: str
    nome_funcao: str
    pontos: float
    ordem: int
    parametros: list[dict[str, Any]]
    retorno: dict[str, Any]
    descricao: str | None = None
    dificuldade: str = "medio"
    max_tentativas: int | None = None
    dicas: list[str] | None = None
    created_at: datetime | None = None


class FuncaoDetailResponse(FuncaoResponse):
    """Response de função com casos de teste."""
    casos_teste: list[CasoTesteResponse] = Field(default_factory=list)
