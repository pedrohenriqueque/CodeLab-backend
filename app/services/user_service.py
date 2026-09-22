"""Casos de uso compartilhados para criação segura de usuários."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import CodelabException
from ..core.security import get_password_hash
from ..models.usuario import PerfilUsuario, Usuario
from ..repositories.user_repository import UserRepository
from ..schemas.usuario import CadastroAlunoRequest, CriarProfessorRequest


async def criar_usuario(
    dados: CadastroAlunoRequest | CriarProfessorRequest,
    perfil: PerfilUsuario,
    db: AsyncSession,
) -> Usuario:
    """Cria usuário com perfil definido pelo caso de uso, não pelo cliente."""
    email = str(dados.email).strip().lower()
    matricula = dados.matricula.strip() if perfil == PerfilUsuario.ALUNO else None
    nome = dados.nome.strip()
    if not nome or (perfil == PerfilUsuario.ALUNO and not matricula):
        raise CodelabException("Nome e matrícula são obrigatórios.", status_code=422)

    repository = UserRepository(db)
    existente = await repository.get_by_email_or_matricula(
        email=email, matricula=matricula
    )
    if existente is not None:
        raise CodelabException(
            "E-mail ou matrícula já cadastrado(a).", status_code=409
        )

    usuario = Usuario(
        nome=nome,
        email=email,
        matricula=matricula,
        senha_hash=get_password_hash(dados.senha),
        perfil=perfil,
    )
    await repository.add(usuario)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise CodelabException(
            "E-mail ou matrícula já cadastrado(a).", status_code=409
        ) from None
    await db.refresh(usuario)
    return usuario
