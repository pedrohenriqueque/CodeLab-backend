from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import get_db
from ..dependencies.authentication import get_current_user
from ..models.usuario import PerfilUsuario, Usuario
from ..schemas.dashboard import DashboardResponse
from ..services.dashboard_service import consultar_dashboard

router = APIRouter(prefix='/turmas', tags=['Dashboard'])


@router.get('/{turma_id}/dashboard/professor', response_model=DashboardResponse)
async def professor_dashboard(turma_id: UUID, usuario: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await consultar_dashboard(turma_id, usuario, PerfilUsuario.PROFESSOR, db)


@router.get('/{turma_id}/dashboard/aluno', response_model=DashboardResponse)
async def aluno_dashboard(turma_id: UUID, usuario: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await consultar_dashboard(turma_id, usuario, PerfilUsuario.ALUNO, db)
