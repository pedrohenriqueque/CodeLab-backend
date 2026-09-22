"""Rotas administrativas de usuários."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import get_db
from ..dependencies.authentication import get_current_user
from ..models.usuario import Usuario
from ..schemas.usuario import AtualizarProfessorRequest, CriarProfessorRequest, UsuarioResponse
from ..services.admin_service import atualizar_professor, criar_professor, desativar_professor, listar_professores

router = APIRouter(prefix="/admin", tags=["Administração"])

def user_response(user: Usuario) -> UsuarioResponse:
    return UsuarioResponse(uuid=user.uuid, nome=user.nome, email=user.email, matricula=user.matricula, perfil=user.perfil.value, ativo=getattr(user, "ativo", True))

@router.get("/professores", response_model=list[UsuarioResponse])
async def list_teacher_accounts(administrador: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[UsuarioResponse]:
    return [user_response(item) for item in await listar_professores(administrador, db)]

@router.post(
    "/professores", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED
)
async def criar_conta_professor(
    dados: CriarProfessorRequest,
    administrador: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsuarioResponse:
    professor = await criar_professor(dados, administrador, db)
    return user_response(professor)


@router.patch("/professores/{professor_id}", response_model=UsuarioResponse)
async def atualizar_conta_professor(
    professor_id: UUID,
    dados: AtualizarProfessorRequest,
    administrador: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsuarioResponse:
    professor = await atualizar_professor(professor_id, dados, administrador, db)
    return user_response(professor)


@router.delete("/professores/{professor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_conta_professor(
    professor_id: UUID,
    administrador: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await desativar_professor(professor_id, administrador, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
