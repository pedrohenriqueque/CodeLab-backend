from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from ..core.schemas import ApiSchema


class CriarTentativaRequest(ApiSchema):
    funcao_atividade_uuid: UUID
    codigo_fonte: str = Field(min_length=1, max_length=100_000)


class TentativaResponse(ApiSchema):
    uuid: UUID
    funcao_atividade_uuid: UUID
    recebida_em: datetime
    avaliada_em: datetime | None
    status: str
    total_casos: int | None
    casos_aprovados: int | None
    falha_tecnica: bool
    nota: Decimal | None
    nota_maxima: Decimal
    melhor_nota_funcao: Decimal | None


class TentativaHistoricoResponse(ApiSchema):
    uuid: UUID
    funcao_atividade_uuid: UUID
    atividade_uuid: UUID
    atividade_titulo: str
    atividade_tipo: str | None = None
    funcao_nome: str
    aluno_nome: str | None = None
    aluno_matricula: str | None = None
    recebida_em: datetime
    avaliada_em: datetime | None = None
    status: str
    nota: Decimal | None = None
    nota_maxima: Decimal | None = None
    casos_aprovados: int | None = None
    total_casos: int | None = None
    falha_tecnica: bool
    codigo_fonte: str | None = None
    resultados_casos: list[dict] | None = None
