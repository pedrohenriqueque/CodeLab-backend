from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import get_db
from ..core.security import create_access_token
from ..schemas.usuario import (
    CadastroAlunoRequest,
    CadastroAlunoResponse,
    LoginResponse,
    UsuarioResponse,
)
from ..services.auth_service import autenticar_usuario, cadastrar_aluno
from ..dependencies.authentication import get_current_user

router = APIRouter(prefix="/auth", tags=["Autenticação"])

@router.get("/me", response_model=UsuarioResponse)
async def me(usuario=Depends(get_current_user)) -> UsuarioResponse:
    return UsuarioResponse(uuid=usuario.uuid, nome=usuario.nome, email=usuario.email, matricula=usuario.matricula, perfil=usuario.perfil.value, ativo=usuario.ativo)


@router.post(
    "/cadastro",
    response_model=CadastroAlunoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def cadastro(
    request: Request,
    dados: CadastroAlunoRequest,
    db: AsyncSession = Depends(get_db),
) -> CadastroAlunoResponse:
    aluno = await cadastrar_aluno(dados, db)

    token = create_access_token(
        {"sub": str(aluno.uuid), "perfil": aluno.perfil.value},
        settings=request.app.state.settings,
    )

    return CadastroAlunoResponse(
        usuario=UsuarioResponse(
            uuid=aluno.uuid,
            nome=aluno.nome,
            email=aluno.email,
            matricula=aluno.matricula,
            perfil=aluno.perfil.value,
            ativo=getattr(aluno, "ativo", True),
        ),
        access_token=token,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    dados: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Autentica por e-mail (campo `username` do formulário OAuth2)."""
    usuario = await autenticar_usuario(dados.username, dados.password, db)
    return LoginResponse(
        access_token=create_access_token(
            {"sub": str(usuario.uuid), "perfil": usuario.perfil.value},
            settings=request.app.state.settings,
        )
    )
