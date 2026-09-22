from datetime import datetime, timedelta, timezone
import logging
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from jose import jwt

from ..config.settings import Settings, get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (UnknownHashError, ValueError, TypeError):
        # Hash invalido/no formato inesperado deve ser tratado como credencial invalida.
        logger.warning("Senha com hash invalido encontrada durante autenticacao.")
        return False


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
    settings: Settings | None = None,
) -> str:
    settings = settings if settings is not None else get_settings()
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key.get_secret_value(), algorithm=settings.algorithm
    )
    return encoded_jwt
