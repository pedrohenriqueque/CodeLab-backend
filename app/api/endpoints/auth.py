from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.dependencies import get_db
from app.core.security import verify_password, create_access_token
from app.db.models import Usuario

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
