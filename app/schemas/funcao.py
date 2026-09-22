from uuid import UUID

from pydantic import Field, model_validator

from ..core.schemas import ApiSchema


TIPOS_ESCALARES = {"int", "long", "float", "double", "char", "bool", "string"}
DIFICULDADES = {"FACIL", "MEDIO", "DIFICIL"}


class ParametroFuncao(ApiSchema):
    nome: str = Field(min_length=1, max_length=100)
    tipo: str = Field(min_length=1, max_length=32)


def validar_tipo(tipo: str, *, permite_vetor: bool) -> str:
    normalized = tipo.strip().lower()
    is_vector = normalized.endswith("[]")
    base_type = normalized[:-2] if is_vector else normalized
    if base_type not in TIPOS_ESCALARES or (is_vector and (not permite_vetor or base_type == "string")):
        raise ValueError("Tipo de C não suportado.")
    return normalized


def validar_parametros(parametros: list[ParametroFuncao]) -> list[ParametroFuncao]:
    names: set[str] = set()
    for parametro in parametros:
        name = parametro.nome.strip()
        if not name.isidentifier() or name in names:
            raise ValueError("Parâmetros devem ter nomes C válidos e distintos.")
        names.add(name)
        validar_tipo(parametro.tipo, permite_vetor=True)
    return parametros


class CriarFuncaoRequest(ApiSchema):
    nome: str = Field(min_length=1, max_length=100)
    enunciado: str = Field(min_length=1, max_length=10000)
    tipo_retorno: str = Field(min_length=1, max_length=32)
    parametros: list[ParametroFuncao] = Field(default_factory=list, max_length=20)
    dificuldade: str = Field(min_length=1, max_length=16)
    compartilhada: bool = True

    @model_validator(mode="after")
    def validar_assinatura(self) -> "CriarFuncaoRequest":
        validar_tipo(self.tipo_retorno, permite_vetor=False)
        validar_parametros(self.parametros)
        if self.dificuldade.strip().upper() not in DIFICULDADES:
            raise ValueError("Dificuldade inválida.")
        return self


class AtualizarFuncaoRequest(ApiSchema):
    nome: str | None = Field(default=None, min_length=1, max_length=100)
    enunciado: str | None = Field(default=None, min_length=1, max_length=10000)
    tipo_retorno: str | None = Field(default=None, min_length=1, max_length=32)
    parametros: list[ParametroFuncao] | None = Field(default=None, max_length=20)
    dificuldade: str | None = Field(default=None, min_length=1, max_length=16)
    compartilhada: bool | None = None

    @model_validator(mode="after")
    def validar_campos(self) -> "AtualizarFuncaoRequest":
        if all(value is None for value in self.model_dump().values()):
            raise ValueError("Informe ao menos um campo para atualização.")
        if self.tipo_retorno is not None:
            validar_tipo(self.tipo_retorno, permite_vetor=False)
        if self.parametros is not None:
            validar_parametros(self.parametros)
        if self.dificuldade is not None and self.dificuldade.strip().upper() not in DIFICULDADES:
            raise ValueError("Dificuldade inválida.")
        return self


class FuncaoResponse(ApiSchema):
    uuid: UUID
    nome: str
    enunciado: str
    tipo_retorno: str
    parametros: list[ParametroFuncao]
    dificuldade: str
    compartilhada: bool
    professor_uuid: UUID
    professor_nome: str
    total_casos_teste: int = 0
