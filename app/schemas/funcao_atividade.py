from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from ..core.schemas import ApiSchema
from .caso_teste import VisibilidadeCaso
from .funcao import DIFICULDADES, ParametroFuncao


class AssociarFuncaoAtividadeRequest(ApiSchema):
    funcao_uuid: UUID
    dificuldade: Literal["FACIL", "MEDIO", "DIFICIL"] | None = None
    nota_maxima: Decimal = Field(gt=0, max_digits=5, decimal_places=2)


class AtualizarFuncaoAtividadeRequest(ApiSchema):
    dificuldade: Literal["FACIL", "MEDIO", "DIFICIL"] | None = None
    nota_maxima: Decimal | None = Field(default=None, gt=0, max_digits=5, decimal_places=2)


class ReordenarFuncoesAtividadeRequest(ApiSchema):
    funcoes_atividade_uuid: list[UUID] = Field(min_length=1, max_length=100)


class CasoTesteAtividadeResponse(ApiSchema):
    uuid: UUID
    entradas: list[Any]
    retorno_esperado: Any
    visibilidade: VisibilidadeCaso
    descricao: str
    peso: Decimal = Decimal("1.00")


class FuncaoAtividadeResponse(ApiSchema):
    uuid: UUID
    nome: str
    enunciado: str
    tipo_retorno: str
    parametros: list[ParametroFuncao]
    dificuldade: str
    nota_maxima: Decimal
    ordem: int
    casos_teste: list[CasoTesteAtividadeResponse]
