from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import CodelabException
from ..core.security import verify_password
from ..models.usuario import Usuario
from ..repositories.user_repository import UserRepository
from ..schemas.usuario import CadastroAlunoRequest
from .user_service import criar_usuario


async def cadastrar_aluno(
    dados: CadastroAlunoRequest,
    db: AsyncSession,
) -> Usuario:
    from ..models.usuario import PerfilUsuario

    return await criar_usuario(dados, PerfilUsuario.ALUNO, db)


async def autenticar_usuario(email: str, senha: str, db: AsyncSession) -> Usuario:
    """Confere credenciais sem revelar se o e-mail existe."""
    usuario = await UserRepository(db).get_by_email(email.strip().lower())
    if usuario is None or not verify_password(senha, usuario.senha_hash):
        raise CodelabException("E-mail ou senha inválidos.", status_code=401)
    return usuario
