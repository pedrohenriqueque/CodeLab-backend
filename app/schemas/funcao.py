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
    """Request body para criar função na biblioteca."""
    model_config = CAMEL_CONFIG

    nome_funcao: str = Field(..., min_length=1, max_length=128, pattern=r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    parametros: list[ParametroSchema] = [ParametroSchema(nome="a", tipo="int")]
    retorno: RetornoSchema = RetornoSchema(tipo="int")
    descricao: str | None = None
    dificuldade_padrao: str = Field(default="medio", pattern=r'^(facil|medio|dificil)$')
    dificuldade: str | None = None  # Compatibilidade retroativa
    pontos: float = 10.0  # Compatibilidade retroativa
    ordem: int = 0  # Compatibilidade retroativa
    max_tentativas: int | None = None  # None = ilimitado
    dicas: list[str] | None = None  # até 3 dicas progressivas


class FuncaoUpdate(BaseModel):
    """Request body para atualizar função na biblioteca."""
    model_config = CAMEL_CONFIG

    nome_funcao: str | None = Field(default=None, min_length=1, max_length=128, pattern=r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    parametros: list[ParametroSchema] | None = None
    retorno: RetornoSchema | None = None
    descricao: str | None = None
    dificuldade_padrao: str | None = Field(default=None, pattern=r'^(facil|medio|dificil)$')
    dificuldade: str | None = None  # Compatibilidade retroativa
    max_tentativas: int | None = None
    dicas: list[str] | None = None


class FuncaoResponse(BaseModel):
    """Response de função."""
    model_config = CAMEL_CONFIG

    uuid: str
    atividade_uuid: str | None = None
    nome_funcao: str
    pontos: float = 10.0
    ordem: int = 0
    parametros: list[dict[str, Any]]
    retorno: dict[str, Any]
    descricao: str | None = None
    dificuldade: str = "medio"
    dificuldade_padrao: str = "medio"
    max_tentativas: int | None = None
    dicas: list[str] | None = None
    total_casos_teste: int = 0
    created_at: datetime | None = None


class FuncaoDetailResponse(FuncaoResponse):
    """Response de função com casos de teste canônicos."""
    casos_teste: list[CasoTesteResponse] = Field(default_factory=list)

