"""Casos de uso exclusivos da administração."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import CodelabException
from ..core.security import get_password_hash
from ..models.usuario import PerfilUsuario, Usuario
from ..schemas.usuario import AtualizarProfessorRequest, CriarProfessorRequest
from .user_service import criar_usuario
from ..repositories.user_repository import UserRepository

async def listar_professores(administrador: Usuario, db: AsyncSession) -> list[Usuario]:
    if administrador.perfil != PerfilUsuario.ADMIN:
        raise CodelabException("Acesso restrito a administrador.", status_code=403)
    return await UserRepository(db).list_professors()


async def criar_professor(
    dados: CriarProfessorRequest, administrador: Usuario, db: AsyncSession
) -> Usuario:
    if administrador.perfil != PerfilUsuario.ADMIN:
        raise CodelabException("Acesso restrito a administrador.", status_code=403)
    return await criar_usuario(dados, PerfilUsuario.PROFESSOR, db)


async def atualizar_professor(
    professor_id: UUID,
    dados: AtualizarProfessorRequest,
    administrador: Usuario,
    db: AsyncSession,
) -> Usuario:
    if administrador.perfil != PerfilUsuario.ADMIN:
        raise CodelabException("Acesso restrito a administrador.", status_code=403)
    professor = await UserRepository(db).get_by_uuid(professor_id)
    if professor is None or professor.perfil != PerfilUsuario.PROFESSOR:
        raise CodelabException("Professor nÃ£o encontrado.", status_code=404)
    if dados.nome is not None:
        professor.nome = dados.nome.strip()
    if dados.email is not None:
        professor.email = str(dados.email).strip().lower()
    if dados.senha is not None:
        professor.senha_hash = get_password_hash(dados.senha)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise CodelabException("E-mail jÃ¡ cadastrado.", status_code=409) from None
    await db.refresh(professor)
    return professor


async def desativar_professor(
    professor_id: UUID, administrador: Usuario, db: AsyncSession
) -> None:
    if administrador.perfil != PerfilUsuario.ADMIN:
        raise CodelabException("Acesso restrito a administrador.", status_code=403)
    professor = await UserRepository(db).get_by_uuid(professor_id)
    if professor is None or professor.perfil != PerfilUsuario.PROFESSOR:
        raise CodelabException("Professor nÃ£o encontrado.", status_code=404)
    professor.ativo = False
    await db.commit()
