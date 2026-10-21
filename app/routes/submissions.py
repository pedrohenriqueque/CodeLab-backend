from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import get_db
from ..dependencies.authentication import get_current_user
from ..integrations.judge0 import Judge0Client
from ..models.usuario import Usuario
from ..repositories.activity_function_repository import ActivityFunctionRepository
from ..repositories.activity_repository import ActivityRepository
from ..schemas.tentativa import CriarTentativaRequest, TentativaHistoricoResponse, TentativaResumoResponse, TentativaResponse
from ..services.submission_service import consultar_tentativa, criar_tentativa, listar_tentativas, resposta_tentativa, resultado_liberado

router = APIRouter(prefix="/submissoes", tags=["Submissões"])


@router.post("", response_model=TentativaResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(dados: CriarTentativaRequest, request: Request, aluno: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> TentativaResponse:
    tentativa = await criar_tentativa(dados, aluno, db, Judge0Client(request.app.state.settings))
    funcao = await ActivityFunctionRepository(db).get_function(tentativa.funcao_atividade_uuid)
    atividade = await ActivityRepository(db).get_by_uuid(funcao.atividade_uuid)
    return TentativaResponse(**await resposta_tentativa(
        tentativa,
        db,
        funcao.nota_maxima,
        liberar_resultado=resultado_liberado(atividade),
    ))


@router.get("", response_model=list[TentativaResumoResponse])
async def list_submissions(
    usuario: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db),
    turma_uuid: UUID | None = Query(default=None, alias="turmaUuid"),
    atividade_uuid: UUID | None = Query(default=None, alias="atividadeUuid"),
    funcao_uuid: UUID | None = Query(default=None, alias="funcaoUuid"),
    aluno_uuid: UUID | None = Query(default=None, alias="alunoUuid"),
    status_filtro: str | None = Query(default=None, alias="status", max_length=32),
) -> list[TentativaResumoResponse]:
    items = await listar_tentativas(
        usuario, db, turma_uuid=turma_uuid, atividade_uuid=atividade_uuid,
        funcao_uuid=funcao_uuid, aluno_uuid=aluno_uuid, status=status_filtro,
    )
    return [TentativaResumoResponse(**item) for item in items]


@router.get("/{attempt_id}", response_model=TentativaHistoricoResponse)
async def get_submission(attempt_id: UUID, usuario: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> TentativaHistoricoResponse:
    return TentativaHistoricoResponse(**await consultar_tentativa(attempt_id, usuario, db))
