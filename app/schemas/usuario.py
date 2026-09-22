from uuid import UUID

from pydantic import EmailStr, Field

from ..core.schemas import ApiSchema


class CadastroAlunoRequest(ApiSchema):
    nome: str = Field(min_length=1, max_length=200)
    email: EmailStr
    matricula: str = Field(min_length=1, max_length=50)
    senha: str = Field(min_length=8)


class CriarProfessorRequest(ApiSchema):
    nome: str = Field(min_length=1, max_length=200)
    email: EmailStr
    senha: str = Field(min_length=8)


class AtualizarProfessorRequest(ApiSchema):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    senha: str | None = Field(default=None, min_length=8)


class UsuarioResponse(ApiSchema):
    uuid: UUID
    nome: str
    email: EmailStr
    matricula: str | None
    perfil: str
    ativo: bool


class CadastroAlunoResponse(ApiSchema):
    usuario: UsuarioResponse
    access_token: str
    token_type: str = "bearer"


class LoginResponse(ApiSchema):
    access_token: str
    token_type: str = "bearer"
