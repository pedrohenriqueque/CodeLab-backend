from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import get_db
from ..dependencies.authentication import get_current_user
from ..models.usuario import Usuario
from ..schemas.progresso import ProgressoAtividadeResponse, ProgressoFuncaoResponse
from ..services.progress_service import consultar_progresso

router = APIRouter(prefix="/atividades", tags=["Progresso"])


@router.get("/{activity_id}/progresso", response_model=ProgressoAtividadeResponse)
async def get_progress(activity_id: UUID, aluno: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> ProgressoAtividadeResponse:
    funcoes = await consultar_progresso(activity_id, aluno, db)
    return ProgressoAtividadeResponse(atividade_uuid=activity_id, funcoes=[ProgressoFuncaoResponse(**item) for item in funcoes])
