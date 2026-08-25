from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.dependencies import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.db.models import Usuario
from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db)
):
    """
    Autentica um usuário (professor ou aluno) e retorna um token JWT.
    
    Nota: OAuth2PasswordRequestForm usa form-data (username e password).
    Para nossa aplicação, mapeamos o campo 'username' para o email do usuário.
    """
    # Buscar usuário pelo email
    result = await session.execute(
        select(Usuario).where(Usuario.email == form_data.username)
    )
    user = result.scalar_one_or_none()
    
    # Verificar senha
    if not user or not verify_password(form_data.password, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Gerar token JWT
    access_token = create_access_token(
        data={"sub": user.uuid, "tipo": user.tipo}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "uuid": user.uuid,
            "nome": user.nome,
            "email": user.email,
            "tipo": user.tipo
        }
    }


class RegisterRequest(BaseModel):
    nome: str = Field(..., min_length=2, max_length=200)
    matricula: str = Field(..., min_length=4, max_length=50)
    email: EmailStr
    senha: str = Field(..., min_length=8)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Cadastra um novo aluno na plataforma.
    """
    # Verificar se email já existe
    result_email = await session.execute(
        select(Usuario).where(Usuario.email == payload.email)
    )
    if result_email.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma conta cadastrada com este e-mail institucional."
        )

    # Verificar se matrícula já existe
    result_mat = await session.execute(
        select(Usuario).where(Usuario.matricula == payload.matricula.strip())
    )
    if result_mat.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um aluno cadastrado com este número de matrícula."
        )

    senha_hash = get_password_hash(payload.senha)

    novo_usuario = Usuario(
        nome=payload.nome.strip(),
        matricula=payload.matricula.strip(),
        email=payload.email.strip().lower(),
        tipo="aluno",
        senha_hash=senha_hash,
    )

    session.add(novo_usuario)
    await session.commit()
    await session.refresh(novo_usuario)

    # Gerar token JWT
    access_token = create_access_token(
        data={"sub": novo_usuario.uuid, "tipo": novo_usuario.tipo}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "uuid": novo_usuario.uuid,
            "nome": novo_usuario.nome,
            "email": novo_usuario.email,
            "tipo": novo_usuario.tipo
        }
    }


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    novaSenha: str = Field(..., min_length=8)


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Redefine a senha de um usuário diretamente pelo e-mail cadastrado.
    """
    result = await session.execute(
        select(Usuario).where(Usuario.email == payload.email.strip().lower())
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma conta encontrada com este endereço de e-mail institucional."
        )

    user.senha_hash = get_password_hash(payload.novaSenha)
    session.add(user)
    await session.commit()

    return {
        "message": "Senha redefinida com sucesso. Você já pode fazer login com suas novas credenciais."
    }



