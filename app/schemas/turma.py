from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from ..core.schemas import ApiSchema


class CriarTurmaRequest(ApiSchema):
    nome: str = Field(min_length=1, max_length=200)


class AtualizarTurmaRequest(ApiSchema):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    ativa: bool | None = None

    @model_validator(mode="after")
    def requires_a_change(self) -> "AtualizarTurmaRequest":
        if self.nome is None and self.ativa is None:
            raise ValueError("Informe ao menos um campo para atualização.")
        return self


class IngressarTurmaRequest(ApiSchema):
    codigo: str = Field(min_length=1, max_length=16)


class TurmaResponse(ApiSchema):
    uuid: UUID
    nome: str
    ativa: bool
    professor_uuid: UUID
    codigo: str | None = None
    total_alunos: int = 0
    total_atividades: int = 0
    inicio_aulas: str | None = None


class AlunoTurmaResponse(ApiSchema):
    uuid: UUID
    nome: str
    email: str
    matricula: str
    atividades_enviadas: int
    total_atividades: int
    media_nota: Decimal | None
    situacao: str


class ResultadoAtividadeTurmaResponse(ApiSchema):
    atividade_uuid: UUID
    titulo: str
    enviados: int
    total_alunos: int
    media_nota: Decimal | None
    aprovacao_percentual: Decimal | None


class ResultadosTurmaResponse(ApiSchema):
    media_geral: Decimal | None
    aprovacao_percentual: Decimal | None
    submissoes_avaliadas: int
    atividades: list[ResultadoAtividadeTurmaResponse]
