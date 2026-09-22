from datetime import datetime
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from ..core.schemas import ApiSchema

class CriarAtividadeRequest(ApiSchema):
    turma_uuid: UUID
    titulo: str = Field(min_length=1, max_length=200)
    descricao: str = Field(default="", max_length=10000)
    inicio_em: datetime
    fim_em: datetime
    tipo: str = Field(default="EXERCICIO", min_length=1, max_length=16)
    permitir_multiplas_submissoes: bool = True
    max_tentativas_por_funcao: int | None = Field(default=None, ge=1, le=50)
    mostrar_ocultos_apos_fechamento: bool = False

    @field_validator("tipo")
    @classmethod
    def validar_tipo(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"EXERCICIO", "PROVA"}:
            raise ValueError("Tipo de atividade inválido.")
        return normalized
    @model_validator(mode="after")
    def validate_dates(self):
        if self.inicio_em >= self.fim_em: raise ValueError("A data inicial deve anteceder a final.")
        return self

class AtualizarAtividadeRequest(ApiSchema):
    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    descricao: str | None = Field(default=None, max_length=10000)
    inicio_em: datetime | None = None
    fim_em: datetime | None = None
    permitir_multiplas_submissoes: bool | None = None
    max_tentativas_por_funcao: int | None = Field(default=None, ge=1, le=50)
    mostrar_ocultos_apos_fechamento: bool | None = None

class AtividadeResponse(ApiSchema):
    uuid: UUID
    turma_uuid: UUID
    titulo: str
    descricao: str
    inicio_em: datetime
    fim_em: datetime
    status: str
    tipo: str
    permitir_multiplas_submissoes: bool
    max_tentativas_por_funcao: int | None
    mostrar_ocultos_apos_fechamento: bool
