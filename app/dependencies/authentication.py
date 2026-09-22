"""Extração segura da identidade autenticada para as rotas."""

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import get_db
from ..models.usuario import Usuario
from ..repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    """Valida o JWT e recupera o usuário pelo `sub` do token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        payload = jwt.decode(
            credentials.credentials,
            request.app.state.settings.secret_key.get_secret_value(),
            algorithms=[request.app.state.settings.algorithm],
        )
        subject = payload.get("sub")
        user_id = UUID(subject) if isinstance(subject, str) else None
    except (JWTError, ValueError, TypeError):
        raise _unauthorized() from None
    if user_id is None:
        raise _unauthorized()

    usuario = await UserRepository(db).get_by_uuid(user_id)
    if usuario is None:
        raise _unauthorized()
    return usuario
