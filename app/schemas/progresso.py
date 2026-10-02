from decimal import Decimal
from uuid import UUID

from ..core.schemas import ApiSchema


class ProgressoFuncaoResponse(ApiSchema):
    funcao_atividade_uuid: UUID
    enviada: bool
    avaliada: bool
    aprovada: bool | None
    melhor_nota: Decimal | None
    total_tentativas: int = 0
    melhor_tentativa_uuid: UUID | None = None
    ultima_tentativa_uuid: UUID | None = None


class ProgressoAtividadeResponse(ApiSchema):
    atividade_uuid: UUID
    funcoes: list[ProgressoFuncaoResponse]
