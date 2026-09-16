"""Schemas Pydantic para Atividade."""

from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.common import CAMEL_CONFIG
from app.schemas.funcao import FuncaoResponse, ParametroSchema, RetornoSchema
from typing import Any


class AtividadeFuncaoCasoTesteConfigSchema(BaseModel):
    """Configuração de inclusão e visibilidade de um caso de teste na atividade."""
    model_config = CAMEL_CONFIG

    caso_teste_uuid: str
    oculto: bool = False


class AtividadeFuncaoAssociarRequest(BaseModel):
    """Request body para associar uma função da biblioteca a uma atividade."""
    model_config = CAMEL_CONFIG

    funcao_uuid: str
    dificuldade: str | None = Field(default=None, pattern=r'^(facil|medio|dificil)$')
    peso: float = 10.0
    ordem: int = 0
    casos_teste: list[AtividadeFuncaoCasoTesteConfigSchema] | None = None


class AtividadeFuncaoUpdateRequest(BaseModel):
    """Request body para atualizar parâmetros da função na atividade."""
    model_config = CAMEL_CONFIG

    dificuldade: str | None = Field(default=None, pattern=r'^(facil|medio|dificil)$')
    peso: float | None = None
    ordem: int | None = None
    casos_teste: list[AtividadeFuncaoCasoTesteConfigSchema] | None = None


class AtividadeFuncaoCasoTesteResponse(BaseModel):
    """Caso de teste configurado na atividade."""
    model_config = CAMEL_CONFIG

    uuid: str
    caso_teste_uuid: str
    numero: int
    oculto: bool = False
    inputs: dict[str, Any] | None = None
    output_esperado: dict[str, Any] | None = None
    descricao: str | None = None


class AtividadeFuncaoResponse(BaseModel):
    """Representação de uma função associada à atividade com dados contextuais."""
    model_config = CAMEL_CONFIG

    uuid: str  # UUID da associação AtividadeFuncao
    funcao_uuid: str
    nome_funcao: str
    descricao: str | None = None
    parametros: list[dict[str, Any]] = []
    retorno: dict[str, Any] = {}
    dificuldade: str
    dificuldade_padrao: str
    peso: float
    ordem: int
    casos_teste: list[AtividadeFuncaoCasoTesteResponse] = []


class AtividadeCreate(BaseModel):
    """Request body para criar atividade."""
    model_config = CAMEL_CONFIG

    titulo: str = Field(..., min_length=1, max_length=300)
    descricao: str | None = None
    pontuacao_maxima: float = 100
    data_abertura: datetime | None = None
    data_fechamento: datetime | None = None
    status: str = "rascunho"
    tipo: str = "exercicio"
    duracao_minutos: int | None = None
    bloquear_paste: bool = False
    notas_liberadas: bool = False


class AtividadeUpdate(BaseModel):
    """Request body para atualizar atividade (PATCH — campos opcionais)."""
    model_config = CAMEL_CONFIG

    titulo: str | None = None
    descricao: str | None = None
    pontuacao_maxima: float | None = None
    data_abertura: datetime | None = None
    data_fechamento: datetime | None = None
    status: str | None = None
    tipo: str | None = None
    duracao_minutos: int | None = None
    bloquear_paste: bool | None = None
    notas_liberadas: bool | None = None


class AtividadeResponse(BaseModel):
    """Response de atividade."""
    model_config = CAMEL_CONFIG

    uuid: str
    professor_uuid: str | None = None
    titulo: str
    descricao: str | None = None
    pontuacao_maxima: float
    data_abertura: datetime | None = None
    data_fechamento: datetime | None = None
    status: str
    tipo: str
    duracao_minutos: int | None = None
    bloquear_paste: bool = False
    notas_liberadas: bool = False
    created_at: datetime | None = None
    status_entrega: str | None = None  # "em_andamento" | "entregue" (para alunos)
    funcoes: list[AtividadeFuncaoResponse | FuncaoResponse] = []


class EntregaAtividadeResponse(BaseModel):
    """Response da entrega final consolidada da atividade (RN14)."""
    model_config = CAMEL_CONFIG

    uuid: str
    aluno_uuid: str
    atividade_uuid: str
    status: str  # "entregue"
    nota_final: float
    data_entrega: datetime
    mensagem: str = "Atividade entregue com sucesso."

