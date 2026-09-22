from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from ..core.schemas import ApiSchema

VisibilidadeCaso = Literal["VISIVEL", "OCULTO"]


class CriarCasoTesteRequest(ApiSchema):
    entradas: list[Any] = Field(max_length=20)
    retorno_esperado: Any
    visibilidade: VisibilidadeCaso
    descricao: str = Field(default="", max_length=1000)


class AtualizarCasoTesteRequest(ApiSchema):
    entradas: list[Any] | None = Field(default=None, max_length=20)
    retorno_esperado: Any | None = None
    visibilidade: VisibilidadeCaso | None = None
    descricao: str | None = Field(default=None, max_length=1000)


class CasoTesteResponse(ApiSchema):
    uuid: UUID
    entradas: list[Any]
    retorno_esperado: Any
    visibilidade: VisibilidadeCaso
    descricao: str
